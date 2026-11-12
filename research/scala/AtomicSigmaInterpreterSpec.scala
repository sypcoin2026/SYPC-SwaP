package io.ergodex.core

import org.scalatest.flatspec.AnyFlatSpec
import org.scalatest.matchers.should.Matchers
import org.ergoplatform._
import org.ergoplatform.validation.ValidationRules
import scorex.crypto.hash.Digest32
import sigmastate.AvlTreeData
import sigmastate.Values.{ByteArrayConstant, ErgoTree, SigmaPropConstant}
import sigmastate.basics.DLogProtocol.DLogProverInput
import sigmastate.eval.{CostingSigmaDslBuilder, IRContext, RuntimeIRContext}
import sigmastate.eval.Extensions._
import sigmastate.interpreter.{ContextExtension, CryptoConstants, ProverResult}
import special.sigma.Header

// Lab-only Sigma 4.0.5 interpreter verification with synthetic UTXOs.
// Not SYPC consensus, a full transaction-validity check, real signatures,
// or an authorization to deploy.
class AtomicSigmaInterpreterSpec extends AnyFlatSpec with Matchers {
  private val ownerPk = DLogProverInput(BigInt(123456789).bigInteger).publicImage
  private val attackerPk = DLogProverInput(BigInt(987654321).bigInteger).publicImage
  private val token = Digest32 @@ Array.fill[Byte](32)(12)
  private val otherToken = Digest32 @@ Array.fill[Byte](32)(13)

  private def ownerTree = ErgoTree.fromProposition(SigmaPropConstant(ownerPk))
  private def attackerTree = ErgoTree.fromProposition(SigmaPropConstant(attackerPk))

  private def candidate(path: String, env: Map[String, Any]): ErgoTree = {
    val fresh = new SigmaPlatform {}
    fresh.compile(fresh.readSource(path), env)
  }

  private def buyScript: ErgoTree = candidate(
    "research/ergo_script/AtomicBuy.sc",
    Map("BuyerPk" -> ownerPk, "TokenId" -> Array.fill[Byte](32)(12), "MinTokenAmount" -> 100L)
  )
  private def sellScript: ErgoTree = candidate(
    "research/ergo_script/AtomicSell.sc",
    Map("SellerPk" -> ownerPk, "MinNativeAmount" -> 1000L)
  )

  private def box(value: Long, tree: ErgoTree,
                  asset: Option[Digest32] = None,
                  amount: Long = 0L,
                  ref: Option[Array[Byte]] = None): ErgoBoxCandidate = {
    val tokens = asset match {
      case Some(id) => Array((id, amount)).toColl
      case None => CostingSigmaDslBuilder.Colls.emptyColl[(Digest32, Long)]
    }
    val registers = ref match {
      case Some(id) => Map(ErgoBox.R4 -> ByteArrayConstant(id))
      case None => Map.empty[ErgoBox.NonMandatoryRegisterId, sigmastate.Values.EvaluatedValue[_ <: sigmastate.SType]]
    }
    new ErgoBoxCandidate(value, tree, 0, tokens, registers)
  }

  private def evaluate(script: ErgoTree, outputs: IndexedSeq[ErgoBoxCandidate] => IndexedSeq[ErgoBoxCandidate]): Boolean = {
    // Use a deterministic synthetic SELF id, generated from the actual Ergo
    // serialization implementation rather than an invented identifier.
    val self = new ErgoBoxCandidate(2000000L, script, 0)
      .toBox(ErgoBox.allZerosModifierId, 0.toShort)
    val tx = ErgoLikeTransaction(
      IndexedSeq(Input(self.id, ProverResult.empty)),
      outputs(IndexedSeq(box(1000000L, ownerTree)))
    )
    val h = 100
    val empty = CostingSigmaDslBuilder.Colls.emptyColl[Byte]
    val preHeader = CPreHeader(
      0, empty, 3L, 0L, h,
      CryptoConstants.dlogGroup.generator, empty
    )
    val ctx = new ErgoLikeContext(
      AvlTreeData.dummy,
      CostingSigmaDslBuilder.Colls.emptyColl[Header],
      preHeader,
      IndexedSeq.empty,
      IndexedSeq(self),
      tx,
      0,
      ContextExtension.empty,
      ValidationRules.currentSettings,
      SigmaConstants.ScriptCostLimit.value,
      0L,
      1.toByte
    )
    implicit val ir: IRContext = new RuntimeIRContext
    val verifier = new ErgoLikeInterpreter
    verifier.verify(script, ctx, ProverResult.empty.proof, Array.fill[Byte](32)(1))
      .toOption.exists(_._1)
  }

  private def buyResult(choice: String): Boolean = {
    val script = buyScript
    val self = new ErgoBoxCandidate(2000000L, script, 0)
      .toBox(ErgoBox.allZerosModifierId, 0.toShort)
    evaluate(script, _ => {
      val recipient = if (choice == "attacker") attackerTree else ownerTree
      val id = if (choice == "other-token") otherToken else token
      val n = if (choice == "underfilled") 99L else 100L
      val r = if (choice == "wrong-ref") Some(Array.fill[Byte](32)(55))
              else if (choice == "no-ref") None else Some(self.id)
      val paid = box(1000000L, recipient, Some(id), n, r)
      if (choice == "no-output") IndexedSeq.empty
      else if (choice == "wrong-index") IndexedSeq(box(1000000L, ownerTree), paid)
      else IndexedSeq(paid)
    })
  }

  private def sellResult(choice: String): Boolean = {
    val script = sellScript
    val self = new ErgoBoxCandidate(2000000L, script, 0)
      .toBox(ErgoBox.allZerosModifierId, 0.toShort)
    evaluate(script, _ => {
      val recipient = if (choice == "attacker") attackerTree else ownerTree
      val amount = if (choice == "underpaid") 999L else 1000L
      val r = if (choice == "wrong-ref") Some(Array.fill[Byte](32)(55))
              else if (choice == "no-ref") None else Some(self.id)
      val paid = box(amount, recipient, ref = r)
      if (choice == "no-output") IndexedSeq.empty
      else if (choice == "wrong-index") IndexedSeq(paid)
      else IndexedSeq(box(1000000L, ownerTree), paid)
    })
  }

  "AtomicBuy with Sigma interpreter" should "accept correct unsigned matching outputs" in {
    buyResult("valid") shouldBe true
  }
  it should "reject wrong asset" in { buyResult("other-token") shouldBe false }
  it should "reject amount below minimum" in { buyResult("underfilled") shouldBe false }
  it should "reject malicious recipient" in { buyResult("attacker") shouldBe false }
  it should "reject missing or incorrect R4 order id" in {
    buyResult("wrong-ref") shouldBe false
    buyResult("no-ref") shouldBe false
  }
  it should "reject incorrectly indexed and absent outputs" in {
    buyResult("wrong-index") shouldBe false
    buyResult("no-output") shouldBe false
  }

  "AtomicSell with Sigma interpreter" should "accept correct unsigned matching outputs" in {
    sellResult("valid") shouldBe true
  }
  it should "reject insufficient payout" in { sellResult("underpaid") shouldBe false }
  it should "reject malicious recipient" in { sellResult("attacker") shouldBe false }
  it should "reject missing or incorrect R4 order id" in {
    sellResult("wrong-ref") shouldBe false
    sellResult("no-ref") shouldBe false
  }
  it should "reject incorrectly indexed and absent outputs" in {
    sellResult("wrong-index") shouldBe false
    sellResult("no-output") shouldBe false
  }
}
