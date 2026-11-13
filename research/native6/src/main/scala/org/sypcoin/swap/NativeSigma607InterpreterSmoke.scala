package org.sypcoin.swap

import java.nio.charset.StandardCharsets.UTF_8
import java.nio.file.{Files, Paths}

import org.ergoplatform._
import org.ergoplatform.validation.ValidationRules
import sigmastate.crypto.DLogProtocol.DLogProverInput
import sigmastate.eval.CPreHeader
import sigmastate.interpreter.{CErgoTreeEvaluator, Interpreter}
import sigma.{Coll, Colls, Header, VersionContext}
import sigma.ast.{ByteArrayConstant, ErgoTree, SigmaPropConstant}
import sigma.crypto.CryptoConstants
import sigma.data.{AvlTreeData, Digest32Coll}
import sigma.interpreter.ContextExtension
import sigma.serialization.{GroupElementSerializer, SigmaSerializer}
import sigma.util.Extensions.EcpOps

/** Executes a *synthetic* SELL fill in the real Sigma 6.0.7 interpreter.
  *
  * Deliberately does NOT submit a SYPC transaction, claim global conservation,
  * validate a network UTXO, pay a fee or contact any live node.
  */
object NativeSigma607InterpreterSmoke {
  private val feeOwner = DLogProverInput(BigInt(123456789).bigInteger)
  private val buyer = DLogProverInput(BigInt(135791113).bigInteger)
  private val sellId = Digest32Coll @@@ Colls.fromArray(Array.fill[Byte](32)(12))
  private val otherId = Digest32Coll @@@ Colls.fromArray(Array.fill[Byte](32)(13))
  private val recipientTree = ErgoTree.fromProposition(SigmaPropConstant(feeOwner.publicImage))
  private val buyerTree = ErgoTree.fromProposition(SigmaPropConstant(buyer.publicImage))
  private val verifier = new ErgoLikeInterpreter {
    override type CTX = ErgoLikeContext
  }
  private val signedMessage = Array.fill[Byte](32)(42)

  private def contracts(path: String): ErgoTree = {
    val file = Paths.get(path).toRealPath()
    require(Files.isRegularFile(file), "SYPC607_SCRIPT_NOT_FOUND")
    val source = new String(Files.readAllBytes(file), UTF_8)
    val env: Map[String, Any] = Map(
      "SellerPk" -> feeOwner.publicImage,
      "SellTokenId" -> Array.fill[Byte](32)(12),
      "SellTokenAmount" -> 10L,
      "MinNativeAmount" -> 1000L,
      "MaxCancelFee" -> 500L,
      "FeePropBytes" -> recipientTree.bytes
    )
    val bytes = NativeSigma607Compile.compile(source, env)
    sigma.serialization.ErgoTreeSerializer.DefaultSerializer.deserializeErgoTree(bytes)
  }

  private def assets(mode: String): Coll[ErgoBox.Token] = mode match {
    case "wrong-token" => Colls.fromArray(Array((otherId, 10L)))
    case "too-few" => Colls.fromArray(Array((sellId, 9L)))
    case "too-many" => Colls.fromArray(Array((sellId, 11L)))
    case "no-tokens" => Colls.emptyColl[ErgoBox.Token]
    case "extra-token" => Colls.fromArray(Array((sellId, 10L), (otherId, 1L)))
    case _ => Colls.fromArray(Array((sellId, 10L)))
  }

  private def evaluate(tree: ErgoTree, scenario: String): Boolean = {
    val tokens = assets(scenario)
    val self = new ErgoBoxCandidate(2000000L, tree, 0, tokens)
      .toBox(ErgoBox.allZerosModifierId, 0.toShort)
    val payer = new ErgoBoxCandidate(1001000L, buyerTree, 0)
      .toBox(ErgoBox.allZerosModifierId, 1.toShort)

    val owner = if (scenario == "wrong-owner") buyerTree else recipientTree
    val payment = if (scenario == "underpay") 2000999L else 2001000L
    val outputTokens = if (scenario == "seller-gets-token")
      Colls.fromArray(Array((otherId, 1L))) else Colls.emptyColl[ErgoBox.Token]
    val r4 = if (scenario == "wrong-order-id")
      ByteArrayConstant(Array.fill[Byte](32)(7))
    else ByteArrayConstant(self.id)
    val mark = if (scenario == "no-order-id") Map.empty[ErgoBox.NonMandatoryRegisterId, sigma.ast.EvaluatedValue[_ <: sigma.ast.SType]]
    else Map[ErgoBox.NonMandatoryRegisterId, sigma.ast.EvaluatedValue[_ <: sigma.ast.SType]](ErgoBox.R4 -> r4)

    val outputs = IndexedSeq(
      new ErgoBoxCandidate(1000000L, buyerTree, 0, tokens),
      new ErgoBoxCandidate(payment, owner, 0, outputTokens, mark)
    )
    val unsigned = UnsignedErgoLikeTransaction(
      IndexedSeq(new UnsignedInput(self.id), new UnsignedInput(payer.id)),
      outputs
    )

    // Conservation here checks only fixture arithmetic; it is NOT a core
    // UTXO validation, mempool check, or actual signed transaction.
    if (scenario == "valid") {
      require(IndexedSeq(self, payer).map(_.value).sum ==
        outputs.map(_.value).sum, "SYPC607_FIXTURE_NATIVE_IMBALANCE")
      require(self.additionalTokens == outputs.head.additionalTokens,
        "SYPC607_FIXTURE_TOKEN_IMBALANCE")
    }

    val context = new ErgoLikeContext(
      AvlTreeData.dummy,
      Colls.emptyColl[Header],
      CPreHeader(0, Colls.emptyColl[Byte], 3L, 0L, 100,
        GroupElementSerializer.parse(SigmaSerializer.startReader(
          GroupElementSerializer.toBytes(CryptoConstants.dlogGroup.generator)
        )).toGroupElement, Colls.emptyColl[Byte]),
      IndexedSeq.empty[ErgoBox],
      IndexedSeq(self, payer),
      unsigned,
      0,
      ContextExtension.empty,
      ValidationRules.currentSettings,
      CErgoTreeEvaluator.DefaultEvalSettings.scriptCostLimitInEvaluator,
      0L,
      VersionContext.MaxSupportedScriptVersion
    )

    verifier.verify(Interpreter.emptyEnv, tree, context,
      Array.empty[Byte], signedMessage).get._1
  }

  def main(args: Array[String]): Unit = {
    require(args.length == 1, "SYPC607_SCRIPT_ROOT_REQUIRED")
    val script = contracts(args(0))
    require(evaluate(script, "valid"), "SYPC607_VALID_SELL_REJECTED")
    println("SIGMA607_INTERPRETER_PASS:valid")

    val bad = Vector("wrong-token", "too-few", "too-many", "no-tokens",
      "extra-token", "underpay", "wrong-owner", "wrong-order-id",
      "no-order-id", "seller-gets-token")
    bad.foreach { scenario =>
      require(!evaluate(script, scenario),
        "SYPC607_MALICIOUS_SELL_ACCEPTED:" + scenario)
      println("SIGMA607_INTERPRETER_REJECT:" + scenario)
    }
    println("SIGMA607_INTERPRETER_SELL_SYNTHETIC_11_CASES_PASS")
    println("NOT_SYPC_NODE_CONSENSUS_NOT_A_FULL_SIGNED_TRANSACTION")
  }
}
