package io.ergodex.core

import org.scalatest.flatspec.AnyFlatSpec
import org.scalatest.matchers.should.Matchers
import org.ergoplatform._
import org.ergoplatform.validation.ValidationRules
import scorex.crypto.hash.Digest32
import scorex.util._
import sigmastate._
import sigmastate.Values.{ByteArrayConstant, ErgoTree, SigmaPropConstant}
import sigmastate.basics.DLogProtocol.DLogProverInput
import sigmastate.eval._
import sigmastate.eval.Extensions._
import sigmastate.interpreter.{ContextExtension, CryptoConstants, ProverInterpreter, ProverResult}
import special.sigma.Header

/**
 * RESEARCH ONLY: actual Sigma signing and verification, with synthetic boxes.
 *
 * Only fixed, publicly known throwaway test secrets are used.  Crucially the
 * ORIGINAL Ergo contract's owner-signature OR branch does not constrain
 * recipients. A valid owner proof therefore accepts a maliciously assembled
 * transaction, if the signer approves that transaction. This is NOT signature
 * forgery: an actual wallet must reject the outputs BEFORE asking the owner
 * to sign. The message here is synthetic; no network or funds are involved.
 */
class AtomicSignedBranchSpec extends AnyFlatSpec with Matchers {
  private val ownerSk = DLogProverInput(BigInt(123456789).bigInteger)
  private val attackerSk = DLogProverInput(BigInt(987654321).bigInteger)
  private def ownerPk = ownerSk.publicImage
  private def ownerTree = ErgoTree.fromProposition(SigmaPropConstant(ownerPk))
  private def attackerTree = ErgoTree.fromProposition(SigmaPropConstant(attackerSk.publicImage))
  private val tokenId = Digest32 @@ Array.fill[Byte](32)(12)
  private val msg = Array.fill[Byte](32)(42)

  private def candidate(side: String): ErgoTree = {
    val platform = new SigmaPlatform {}
    if (side == "buy")
      platform.compile(platform.readSource("research/ergo_script/AtomicBuy.sc"),
        Map("BuyerPk" -> ownerPk, "TokenId" -> Array.fill[Byte](32)(12), "MinTokenAmount" -> 100L))
    else
      platform.compile(platform.readSource("research/ergo_script/AtomicSell.sc"),
        Map("SellerPk" -> ownerPk, "MinNativeAmount" -> 1000L))
  }

  private def context(script: ErgoTree, recipient: ErgoTree): ErgoLikeContext = {
    val self = new ErgoBoxCandidate(2000000L, script, 0)
      .toBox(ErgoBox.allZerosModifierId, 0.toShort)
    // Only one synthetic recipient output, intentionally missing the required
    // buy/sell fulfillment. The owner-signature branch must still reduce to
    // ownerPk. This models UI/deception risk, not an attacker forging proof.
    val outputs = IndexedSeq(
      new ErgoBoxCandidate(1950000L, recipient, 0),
      // A second output prevents the legacy seller from evaluating an
      // out-of-range OUTPUTS(1). It is intentionally underpaid and carries
      // R4 so fill remains invalid and ONLY the owner's real signature can
      // authorize the spend. No funds or consensus are involved.
      new ErgoBoxCandidate(
        1L, recipient, 0,
        additionalRegisters = Map(ErgoBox.R4 -> ByteArrayConstant(self.id))
      )
    )
    val tx = ErgoLikeTransaction(IndexedSeq(Input(self.id, ProverResult.empty)), outputs)
    val empty = CostingSigmaDslBuilder.Colls.emptyColl[Byte]
    val preHeader = CPreHeader(
      0, empty, 3L, 0L, 100,
      CryptoConstants.dlogGroup.generator, empty
    )
    new ErgoLikeContext(
      AvlTreeData.dummy,
      CostingSigmaDslBuilder.Colls.emptyColl[Header],
      preHeader, IndexedSeq.empty, IndexedSeq(self), tx, 0,
      ContextExtension.empty, ValidationRules.currentSettings,
      SigmaConstants.ScriptCostLimit.value, 0L, 1.toByte
    )
  }

  private def check(side: String, signer: DLogProverInput,
                    recipient: ErgoTree, verifierMessage: Array[Byte]): (Boolean, Boolean, Boolean) = {
    val script = candidate(side)
    val ctx = context(script, recipient)
    implicit val ir: IRContext = new RuntimeIRContext
    val prover = new ErgoLikeInterpreter with ProverInterpreter {
      override type CTX = ErgoLikeContext
      override val secrets = Seq(signer)
    }
    val verifier = new ErgoLikeInterpreter { override type CTX = ErgoLikeContext }
    val empty = verifier.verify(script, ctx, ProverResult.empty, msg)
      .toOption.exists(_._1)
    val proven = prover.prove(script, ctx, msg)
    val success = proven.toOption.exists(p => verifier.verify(script, ctx, p, verifierMessage)
      .toOption.exists(_._1))
    (empty, success, proven.isSuccess)
  }

  "Original AtomicBuy" should "require owner proof when fill is absent" in {
    val (unsigned, ownerSigned, generated) = check("buy", ownerSk, ownerTree, msg)
    unsigned shouldBe false
    ownerSigned shouldBe true
    generated shouldBe true
  }

  it should "reject a stranger's attempted signature" in {
    val (_, valid, _) = check("buy", attackerSk, attackerTree, msg)
    valid shouldBe false
  }

  it should "reject an owner proof over a different message" in {
    val (_, valid, _) = check("buy", ownerSk, ownerTree, Array.fill[Byte](32)(43))
    valid shouldBe false
  }

  it should "allow an owner-signed malicious recipient (known design limitation)" in {
    val (_, valid, _) = check("buy", ownerSk, attackerTree, msg)
    valid shouldBe true
  }

  "Original AtomicSell" should "require owner proof when payout is absent" in {
    val (unsigned, ownerSigned, generated) = check("sell", ownerSk, ownerTree, msg)
    unsigned shouldBe false
    ownerSigned shouldBe true
    generated shouldBe true
  }

  it should "reject a stranger's attempted signature" in {
    val (_, valid, _) = check("sell", attackerSk, attackerTree, msg)
    valid shouldBe false
  }

  it should "reject an owner proof over a different message" in {
    val (_, valid, _) = check("sell", ownerSk, ownerTree, Array.fill[Byte](32)(43))
    valid shouldBe false
  }

  it should "allow an owner-signed malicious recipient (known design limitation)" in {
    val (_, valid, _) = check("sell", ownerSk, attackerTree, msg)
    valid shouldBe true
  }
}
