package org.sypcoin.swap

import java.nio.charset.StandardCharsets.UTF_8
import java.nio.file.{Files, Paths}
import java.security.MessageDigest

import org.ergoplatform._
import org.ergoplatform.validation.ValidationRules
import scorex.util.encode.Base16
import sigma.{Colls, Header, VersionContext}
import sigma.ast.{ByteArrayConstant, ErgoTree, EvaluatedValue, SType, SigmaPropConstant}
import sigma.crypto.CryptoConstants
import sigma.data.{AvlTreeData, Digest32Coll}
import sigma.interpreter.{ContextExtension, ProverResult}
import sigma.serialization.{GroupElementSerializer, SigmaSerializer}
import sigma.util.Extensions.EcpOps
import sigmastate.crypto.DLogProtocol.DLogProverInput
import sigmastate.eval.CPreHeader
import sigmastate.interpreter.{CErgoTreeEvaluator, Interpreter, ProverInterpreter}

import scala.util.Try

/** Full SERIALIZED, two-input, Sigma-SIGNED synthetic SELL transaction.
  *
  * Both input proofs are generated against the SAME unsigned transaction
  * messageToSign, then independently verified after signed serialization.
  *
  * This is NOT SYPC Core's native transaction admission or network consensus:
  * it does not query a real UTXO set, enforce network minimum box values,
  * prove protocol fees, cover mempool conflicts or deploy a smart contract.
  * Deterministic PRIVATE test scalars are PUBLIC. Never use them for money.
  */
object NativeSigma607SignedTx {
  private val ownerSecret = DLogProverInput(BigInt(123456789).bigInteger)
  private val buyerSecret = DLogProverInput(BigInt(135791113).bigInteger)
  private val outsiderSecret = DLogProverInput(BigInt(42424242).bigInteger)
  private val ownerTree = ErgoTree.fromProposition(SigmaPropConstant(ownerSecret.publicImage))
  private val buyerTree = ErgoTree.fromProposition(SigmaPropConstant(buyerSecret.publicImage))
  private val feeTree = ErgoTree.fromProposition(SigmaPropConstant(outsiderSecret.publicImage))
  private val tokenId = Digest32Coll @@@ Colls.fromArray(Array.fill[Byte](32)(12))
  private val sellTokens = Colls.fromArray(Array((tokenId, 10L)))

  private val verifier = new ErgoLikeInterpreter {
    override type CTX = ErgoLikeContext
  }
  private val buyerProver = new ErgoLikeInterpreter with ProverInterpreter {
    override type CTX = ErgoLikeContext
    override val secrets = Seq(buyerSecret)
  }
  private val outsiderProver = new ErgoLikeInterpreter with ProverInterpreter {
    override type CTX = ErgoLikeContext
    override val secrets = Seq(outsiderSecret)
  }

  private def contract(path: String): ErgoTree = {
    val source = Paths.get(path).toRealPath()
    require(Files.isRegularFile(source) && !Files.isSymbolicLink(source),
      "SYPC607_SIGNED_SOURCE_NOT_REGULAR")
    val text = new String(Files.readAllBytes(source), UTF_8)
    val env = Map[String, Any](
      "SellerPk" -> ownerSecret.publicImage,
      "SellTokenId" -> Array.fill[Byte](32)(12),
      "SellTokenAmount" -> 10L,
      "MinNativeAmount" -> 1000L,
      "MaxCancelFee" -> 500L,
      "FeePropBytes" -> feeTree.bytes
    )
    sigma.serialization.ErgoTreeSerializer.DefaultSerializer.deserializeErgoTree(
      NativeSigma607Compile.compile(text, env)
    )
  }

  private def mark(orderId: Array[Byte]) =
    Map[ErgoBox.NonMandatoryRegisterId, EvaluatedValue[_ <: SType]](
      ErgoBox.R4 -> ByteArrayConstant(orderId)
    )

  private case class Fixture(
    order: ErgoBox, funding: ErgoBox,
    unsigned: UnsignedErgoLikeTransaction
  ) {
    def boxes: IndexedSeq[ErgoBox] = IndexedSeq(order, funding)
    def txMessage: Array[Byte] = unsigned.messageToSign
  }

  private def create(tree: ErgoTree): Fixture = {
    val order = new ErgoBoxCandidate(2000000L, tree, 0, sellTokens)
      .toBox(ErgoBox.allZerosModifierId, 0.toShort)
    val funding = new ErgoBoxCandidate(1001200L, buyerTree, 0)
      .toBox(ErgoBox.allZerosModifierId, 1.toShort)
    val outputs = IndexedSeq(
      new ErgoBoxCandidate(1000000L, buyerTree, 0, sellTokens),
      new ErgoBoxCandidate(2001000L, ownerTree, 0,
        Colls.emptyColl[ErgoBox.Token], mark(order.id)),
      new ErgoBoxCandidate(200L, feeTree, 0)
    )
    Fixture(order, funding, UnsignedErgoLikeTransaction(
      IndexedSeq(new UnsignedInput(order.id), new UnsignedInput(funding.id)),
      outputs
    ))
  }

  private def context(f: Fixture, tx: ErgoLikeTransactionTemplate[_ <: UnsignedInput],
                      index: Int): ErgoLikeContext = new ErgoLikeContext(
    AvlTreeData.dummy, Colls.emptyColl[Header],
    CPreHeader(0, Colls.emptyColl[Byte], 3L, 0L, 100,
      GroupElementSerializer.parse(SigmaSerializer.startReader(
        GroupElementSerializer.toBytes(CryptoConstants.dlogGroup.generator)
      )).toGroupElement, Colls.emptyColl[Byte]),
    IndexedSeq.empty[ErgoBox], f.boxes, tx, index,
    ContextExtension.empty, ValidationRules.currentSettings,
    CErgoTreeEvaluator.DefaultEvalSettings.scriptCostLimitInEvaluator,
    0L, VersionContext.MaxSupportedScriptVersion
  )

  private def tokens(boxes: Iterable[ErgoBoxCandidate]): Map[String, BigInt] =
    boxes.flatMap(_.additionalTokens.toArray).foldLeft(Map.empty[String, BigInt]) {
      case (acc, (id, qty)) =>
        val key = Base16.encode(id.toArray)
        acc.updated(key, acc.getOrElse(key, BigInt(0)) + BigInt(qty))
    }

  private def conserve(f: Fixture, tx: ErgoLikeTransactionTemplate[_ <: UnsignedInput]): Unit = {
    val inNative = f.boxes.foldLeft(BigInt(0))((acc, b) => acc + b.value)
    val outNative = tx.outputCandidates.foldLeft(BigInt(0))((acc, b) => acc + b.value)
    require(inNative == outNative, "SYPC607_SIGNED_NATIVE_IMBALANCE")
    require(tokens(f.boxes) == tokens(tx.outputCandidates),
      "SYPC607_SIGNED_TOKEN_IMBALANCE")
    require(tx.inputs.map(_.boxId.toVector).distinct.size == tx.inputs.size,
      "SYPC607_SIGNED_DUPLICATE_INPUT")
  }

  private def signed(f: Fixture): ErgoLikeTransaction = {
    val msg = f.txMessage
    val freeFill = buyerProver.prove(f.order.ergoTree, context(f, f.unsigned, 0), msg).get
    val buyerProof = buyerProver.prove(f.funding.ergoTree, context(f, f.unsigned, 1), msg).get
    require(buyerProof.proof.nonEmpty, "SYPC607_SIGNED_BUYER_PROOF_EMPTY")
    require(freeFill.proof.isEmpty, "SYPC607_SIGNED_ORDER_FILL_REQUIRES_PROOF")
    val signedTx = f.unsigned.toSigned(IndexedSeq(freeFill, buyerProof))
    require(java.util.Arrays.equals(signedTx.messageToSign, msg),
      "SYPC607_SIGNED_MESSAGE_CHANGED")
    conserve(f, signedTx)
    val raw = ErgoLikeTransactionSerializer.toBytes(signedTx)
    val decoded = ErgoLikeTransactionSerializer.parse(SigmaSerializer.startReader(raw))
    require(java.util.Arrays.equals(decoded.messageToSign, msg),
      "SYPC607_SIGNED_SERIALIZED_MESSAGE_CHANGED")
    require(decoded.inputs(1).spendingProof.proof.sameElements(buyerProof.proof),
      "SYPC607_SIGNED_SERIALIZED_PROOF_CHANGED")
    decoded
  }

  private def verifyInput(f: Fixture, tx: ErgoLikeTransaction, index: Int): Boolean =
    verifier.verify(Interpreter.emptyEnv, f.boxes(index).ergoTree,
      context(f, tx, index), tx.inputs(index).spendingProof, tx.messageToSign
    ).get._1

  private def mismatch(f: Fixture, original: ErgoLikeTransaction, kind: String): Boolean = {
    val candidate = kind match {
      case "missing-buyer-proof" =>
        ErgoLikeTransaction(IndexedSeq(
          original.inputs(0), Input(f.funding.id, ProverResult.empty)),
          original.outputCandidates)
      case "wrong-buyer-proof" =>
        val rogue = outsiderProver.prove(feeTree, context(f, f.unsigned, 1),
          f.txMessage).get
        ErgoLikeTransaction(IndexedSeq(
          original.inputs(0), Input(f.funding.id, rogue)),
          original.outputCandidates)
      case "changed-seller-payout" =>
        val outs = original.outputCandidates.updated(1,
          new ErgoBoxCandidate(2001001L, ownerTree, 0,
            Colls.emptyColl[ErgoBox.Token], mark(f.order.id)))
        ErgoLikeTransaction(original.inputs, outs)
      case "wrong-order-register" =>
        val outs = original.outputCandidates.updated(1,
          new ErgoBoxCandidate(2001000L, ownerTree, 0,
            Colls.emptyColl[ErgoBox.Token],
            mark(Array.fill[Byte](32)(7))))
        ErgoLikeTransaction(original.inputs, outs)
      case "modified-token-recipient" =>
        val outs = original.outputCandidates.updated(0,
          new ErgoBoxCandidate(1000000L, ownerTree, 0, sellTokens))
        ErgoLikeTransaction(original.inputs, outs)
      case "duplicate-order-input" =>
        ErgoLikeTransaction(IndexedSeq(
          original.inputs(0), Input(f.order.id, original.inputs(1).spendingProof)),
          original.outputCandidates)
      case other => throw new IllegalArgumentException("Unsupported negative case: " + other)
    }
    kind match {
      case "duplicate-order-input" =>
        // Independent transaction shape guard: duplicated inputs are invalid,
        // even if a standalone script check were to return true.
        candidate.inputs.map(_.boxId.toVector).distinct.size == candidate.inputs.size
      case _ =>
        // An invalid tx must not be accepted for BOTH spending inputs.
        val orderOk = Try(verifyInput(f, candidate, 0)).getOrElse(false)
        val buyerOk = Try(verifyInput(f, candidate, 1)).getOrElse(false)
        orderOk && buyerOk
    }
  }

  def main(args: Array[String]): Unit = {
    require(args.length == 1, "SYPC607_SIGNED_SELL_PATH_REQUIRED")
    val tree = contract(args(0))
    val f = create(tree)
    val transaction = signed(f)
    require(verifyInput(f, transaction, 0),
      "SYPC607_SIGNED_ORDER_PROOF_REJECTED")
    require(verifyInput(f, transaction, 1),
      "SYPC607_SIGNED_BUYER_PROOF_REJECTED")
    require(f.boxes.size == transaction.inputs.size, "SYPC607_SIGNED_INPUT_SHAPE")
    require(transaction.outputCandidates.size == 3, "SYPC607_SIGNED_OUTPUT_SHAPE")
    println("SIGMA607_SIGNED_PASS:both_inputs")
    println("SIGMA607_SIGNED_SERIALIZATION_PASS")
    println("SIGMA607_SIGNED_CONSERVATION_PASS")

    val invalid = Vector(
      "missing-buyer-proof", "wrong-buyer-proof", "changed-seller-payout",
      "wrong-order-register", "modified-token-recipient",
      "duplicate-order-input"
    )
    invalid.foreach { name =>
      require(!mismatch(f, transaction, name),
        "SYPC607_SIGNED_UNSAFE_TRANSACTION_ACCEPTED:" + name)
      println("SIGMA607_SIGNED_REJECT:" + name)
    }
    println("SIGMA607_SIGNED_SYNTHETIC_7_CASES_PASS")
    println("NOT_SYPC_CORE_CONSENSUS_NOT_MEMPOOL_NOT_MINBOX_NOT_LIVENESS")
  }
}
