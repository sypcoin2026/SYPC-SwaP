package org.sypcoin.swap

import java.nio.charset.StandardCharsets.UTF_8
import java.nio.file.{Files, Paths}

import org.ergoplatform._
import org.ergoplatform.validation.ValidationRules
import sigma.{Coll, Colls, Header, VersionContext}
import sigma.ast.{ErgoTree, SigmaPropConstant}
import sigma.crypto.CryptoConstants
import sigma.data.{AvlTreeData, Digest32Coll}
import sigma.interpreter.{ContextExtension, ProverResult}
import sigma.serialization.{GroupElementSerializer, SigmaSerializer}
import sigma.util.Extensions.EcpOps
import sigmastate.crypto.DLogProtocol.DLogProverInput
import sigmastate.eval.CPreHeader
import sigmastate.interpreter.{CErgoTreeEvaluator, Interpreter, ProverInterpreter}

import scala.util.Try

/** Two genuine owner Schnorr proofs: sell-order cancellation + sponsor UTXO.
  *
  * Sigma 6.0.7 only. No network I/O, no real wallets, no node, no fee/min-box
  * admission, no guarantee that a minimum-value order is ever recoverable.
  * All secret scalars below are intentionally public/synthetic.
  */
object NativeSigma607SponsoredCancel {
  private val ownerKey = DLogProverInput(BigInt(123456789).bigInteger)
  private val outsiderKey = DLogProverInput(BigInt(42424242).bigInteger)
  private val ownerTree = ErgoTree.fromProposition(SigmaPropConstant(ownerKey.publicImage))
  private val feeTree = ErgoTree.fromProposition(SigmaPropConstant(outsiderKey.publicImage))
  private val tokenId = Digest32Coll @@@ Colls.fromArray(Array.fill[Byte](32)(12))
  private val otherId = Digest32Coll @@@ Colls.fromArray(Array.fill[Byte](32)(13))
  private val lockedTokens: Coll[ErgoBox.Token] =
    Colls.fromArray(Array((tokenId, 10L)))

  private val ownerSigner = new ErgoLikeInterpreter with ProverInterpreter {
    override type CTX = ErgoLikeContext
    override val secrets = Seq(ownerKey)
  }
  private val outsiderSigner = new ErgoLikeInterpreter with ProverInterpreter {
    override type CTX = ErgoLikeContext
    override val secrets = Seq(outsiderKey)
  }
  private val verifier = new ErgoLikeInterpreter {
    override type CTX = ErgoLikeContext
  }

  private def script(path: String): ErgoTree = {
    val file = Paths.get(path).toRealPath()
    require(Files.isRegularFile(file) && !Files.isSymbolicLink(file),
      "SYPC607_CANCEL_SOURCE_INVALID")
    val source = new String(Files.readAllBytes(file), UTF_8)
    val env: Map[String, Any] = Map(
      "SellerPk" -> ownerKey.publicImage,
      "SellTokenId" -> Array.fill[Byte](32)(12),
      "SellTokenAmount" -> 10L,
      "MinNativeAmount" -> 1000L,
      "MaxCancelFee" -> 500L,
      "FeePropBytes" -> feeTree.bytes
    )
    sigma.serialization.ErgoTreeSerializer.DefaultSerializer.deserializeErgoTree(
      NativeSigma607Compile.compile(source, env)
    )
  }

  private case class Fixture(order: ErgoBox, sponsor: ErgoBox,
                             unsigned: UnsignedErgoLikeTransaction) {
    def inputs: IndexedSeq[ErgoBox] = IndexedSeq(order, sponsor)
  }

  private def make(tree: ErgoTree, sponsorNative: Long = 1000L,
                   feeNative: Long = 200L, sponsorToken: Boolean = false,
                   feeScript: ErgoTree = feeTree,
                   refundScript: ErgoTree = ownerTree): Fixture = {
    val order = new ErgoBoxCandidate(2000000L, tree, 0, lockedTokens)
      .toBox(ErgoBox.allZerosModifierId, 0.toShort)
    val extra = if (sponsorToken)
      Colls.fromArray(Array((otherId, 1L))) else Colls.emptyColl[ErgoBox.Token]
    val sponsor = new ErgoBoxCandidate(sponsorNative, ownerTree, 0, extra)
      .toBox(ErgoBox.allZerosModifierId, 1.toShort)
    val refundNative = Math.subtractExact(Math.addExact(order.value, sponsorNative), feeNative)
    val refund = new ErgoBoxCandidate(refundNative, refundScript, 0, lockedTokens)
    val fee = new ErgoBoxCandidate(feeNative, feeScript, 0)
    val tx = UnsignedErgoLikeTransaction(
      IndexedSeq(new UnsignedInput(order.id), new UnsignedInput(sponsor.id)),
      IndexedSeq(refund, fee)
    )
    Fixture(order, sponsor, tx)
  }

  private def context(f: Fixture, tx: ErgoLikeTransactionTemplate[_ <: UnsignedInput],
                      index: Int): ErgoLikeContext = new ErgoLikeContext(
    AvlTreeData.dummy, Colls.emptyColl[Header],
    CPreHeader(0, Colls.emptyColl[Byte], 3L, 0L, 100,
      GroupElementSerializer.parse(SigmaSerializer.startReader(
        GroupElementSerializer.toBytes(CryptoConstants.dlogGroup.generator)
      )).toGroupElement, Colls.emptyColl[Byte]),
    IndexedSeq.empty[ErgoBox], f.inputs, tx, index,
    ContextExtension.empty, ValidationRules.currentSettings,
    CErgoTreeEvaluator.DefaultEvalSettings.scriptCostLimitInEvaluator,
    0L, VersionContext.MaxSupportedScriptVersion
  )

  private def checkConservation(f: Fixture): Unit = {
    val inNative = f.inputs.foldLeft(BigInt(0))((acc, b) => acc + b.value)
    val outNative = f.unsigned.outputCandidates.foldLeft(BigInt(0))((acc, b) => acc + b.value)
    require(inNative == outNative, "SYPC607_CANCEL_NATIVE_IMBALANCE")
    require(f.order.additionalTokens == f.unsigned.outputCandidates(0).additionalTokens,
      "SYPC607_CANCEL_TOKEN_REFUND_MISMATCH")
    require(f.sponsor.additionalTokens.isEmpty, "SYPC607_CANCEL_SPONSOR_NOT_NATIVE_ONLY")
    require(f.unsigned.outputCandidates(1).additionalTokens.isEmpty,
      "SYPC607_CANCEL_FEE_CONTAINS_TOKENS")
    require(f.unsigned.outputCandidates(0).value >= f.order.value,
      "SYPC607_CANCEL_ORDER_COLLATERAL_NOT_PRESERVED")
  }

  private def sign(f: Fixture): ErgoLikeTransaction = {
    checkConservation(f)
    val message = f.unsigned.messageToSign
    val ownerProof = ownerSigner.prove(f.order.ergoTree, context(f, f.unsigned, 0), message).get
    val sponsorProof = ownerSigner.prove(f.sponsor.ergoTree, context(f, f.unsigned, 1), message).get
    require(ownerProof.proof.nonEmpty, "SYPC607_CANCEL_ORDER_PROOF_MISSING")
    require(sponsorProof.proof.nonEmpty, "SYPC607_CANCEL_SPONSOR_PROOF_MISSING")
    val signed = f.unsigned.toSigned(IndexedSeq(ownerProof, sponsorProof))
    require(java.util.Arrays.equals(signed.messageToSign, message),
      "SYPC607_CANCEL_SIGNED_MESSAGE_CHANGED")
    val raw = ErgoLikeTransactionSerializer.toBytes(signed)
    val restored = ErgoLikeTransactionSerializer.parse(SigmaSerializer.startReader(raw))
    require(java.util.Arrays.equals(restored.messageToSign, message),
      "SYPC607_CANCEL_SERIALIZED_MESSAGE_CHANGED")
    require(restored.inputs(0).spendingProof.proof.sameElements(ownerProof.proof) &&
      restored.inputs(1).spendingProof.proof.sameElements(sponsorProof.proof),
      "SYPC607_CANCEL_PROOFS_CHANGED")
    restored
  }

  private def verifies(f: Fixture, signed: ErgoLikeTransaction, index: Int): Boolean =
    verifier.verify(Interpreter.emptyEnv, f.inputs(index).ergoTree,
      context(f, signed, index), signed.inputs(index).spendingProof,
      signed.messageToSign).get._1

  private def tampered(f: Fixture, signed: ErgoLikeTransaction, which: String): Boolean = {
    val altered = which match {
      case "missing-order-proof" =>
        ErgoLikeTransaction(IndexedSeq(
          Input(f.order.id, ProverResult.empty), signed.inputs(1)),
          signed.outputCandidates)
      case "missing-sponsor-proof" =>
        ErgoLikeTransaction(IndexedSeq(
          signed.inputs(0), Input(f.sponsor.id, ProverResult.empty)),
          signed.outputCandidates)
      case "foreign-sponsor-proof" =>
        val foreign = outsiderSigner.prove(feeTree, context(f, f.unsigned, 1),
          f.unsigned.messageToSign).get
        ErgoLikeTransaction(IndexedSeq(
          signed.inputs(0), Input(f.sponsor.id, foreign)),
          signed.outputCandidates)
      case "redirect-refund-after-signature" =>
        val refund = new ErgoBoxCandidate(2000800L, feeTree, 0, lockedTokens)
        ErgoLikeTransaction(signed.inputs, signed.outputCandidates.updated(0, refund))
      case other => throw new IllegalArgumentException("Unknown mutation: " + other)
    }
    Try(verifies(f, altered, 0)).getOrElse(false) &&
      Try(verifies(f, altered, 1)).getOrElse(false)
  }

  private def rejectsContract(f: Fixture): Boolean = {
    // If an invalid cancellation can be signed by the owner despite all
    // constraints, the test must FAIL rather than merely logging success.
    ownerSigner.prove(f.order.ergoTree, context(f, f.unsigned, 0),
      f.unsigned.messageToSign).isFailure
  }

  def main(args: Array[String]): Unit = {
    require(args.length == 1, "SYPC607_CANCEL_SCRIPT_REQUIRED")
    val tree = script(args(0))
    val f = make(tree)
    val signed = sign(f)
    require(verifies(f, signed, 0), "SYPC607_CANCEL_ORDER_SIGNATURE_FAILED")
    require(verifies(f, signed, 1), "SYPC607_CANCEL_SPONSOR_SIGNATURE_FAILED")
    println("SIGMA607_CANCEL_PASS:two_owner_signatures")
    println("SIGMA607_CANCEL_SERIALIZATION_PASS")
    println("SIGMA607_CANCEL_CONSERVATION_PASS")

    val tamperedCases = Vector(
      "missing-order-proof", "missing-sponsor-proof",
      "foreign-sponsor-proof", "redirect-refund-after-signature"
    )
    tamperedCases.foreach { scenario =>
      require(!tampered(f, signed, scenario),
        "SYPC607_CANCEL_UNSAFE_SIGNED_TRANSACTION:" + scenario)
      println("SIGMA607_CANCEL_REJECT:" + scenario)
    }

    val malformed = Vector(
      "fee-over-cap" -> make(tree, feeNative = 501L),
      "sponsor-insufficient" -> make(tree, sponsorNative = 100L),
      "sponsor-with-tokens" -> make(tree, sponsorToken = true),
      "wrong-fee-script" -> make(tree, feeScript = ownerTree)
    )
    malformed.foreach { case (scenario, sample) =>
      require(rejectsContract(sample),
        "SYPC607_CANCEL_UNSAFE_CONTRACT_ACCEPTED:" + scenario)
      println("SIGMA607_CANCEL_REJECT:" + scenario)
    }
    println("SIGMA607_CANCEL_SYNTHETIC_9_CASES_PASS")
    println("NOT_SYPC_CORE_CONSENSUS_NOT_REAL_LIVENESS_NOT_MINBOX_OR_FEES")
  }
}
