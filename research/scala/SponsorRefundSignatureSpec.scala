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
import special.collection._
import special.sigma.Header

/**
 * Experimental refund-guard scripts, Sigma 4.0.5 only, synthetic UTXOs.
 * Deliberately no SYPC node, network, real keys, or real funds.
 * This does NOT test full transaction balance, dust, double spends or liveness.
 */
class SponsorRefundSignatureSpec extends AnyFlatSpec with Matchers {
  private val ownerSk = DLogProverInput(BigInt(123456789).bigInteger)
  private val feeSk = DLogProverInput(BigInt(987654321).bigInteger)
  private val thirdSk = DLogProverInput(BigInt(135791113).bigInteger)
  private val ownerTree = ErgoTree.fromProposition(SigmaPropConstant(ownerSk.publicImage))
  private val feeTree = ErgoTree.fromProposition(SigmaPropConstant(feeSk.publicImage))
  private val thirdTree = ErgoTree.fromProposition(SigmaPropConstant(thirdSk.publicImage))
  private val tokenId = Digest32 @@ Array.fill[Byte](32)(12)
  private val otherToken = Digest32 @@ Array.fill[Byte](32)(13)
  private val msg = Array.fill[Byte](32)(42)

  private def tokens(id: Digest32, count: Long): Coll[(Digest32, Long)] = {
    Array((id, count)).toColl
  }
  private def noTokens: Coll[(Digest32, Long)] =
    CostingSigmaDslBuilder.Colls.emptyColl[(Digest32, Long)]

  private def script(side: String): ErgoTree = {
    val platform = new SigmaPlatform {}
    val source = platform.readSource(
      if (side == "buy") "research/ergo_script/AtomicBuySponsorRefund.sc"
      else "research/ergo_script/AtomicSellSponsorRefund.sc"
    )
    val common: Map[String, Any] = Map(
      "MaxCancelFee" -> 100L, "FeePropBytes" -> feeTree.bytes
    )
    val env = if (side == "buy")
      common ++ Map[String, Any](
        "BuyerPk" -> ownerSk.publicImage,
        "TokenId" -> Array.fill[Byte](32)(12),
        "MinTokenAmount" -> 100L
      )
      else common ++ Map[String, Any](
        "SellerPk" -> ownerSk.publicImage,
        "SellTokenId" -> Array.fill[Byte](32)(12),
        "SellTokenAmount" -> 10L,
        "MinNativeAmount" -> 1000L
      )
    platform.compile(source, env)
  }

  private def context(side: String, scenario: String): (ErgoTree, ErgoLikeContext) = {
    val tree = script(side)
    val locked = if (side == "sell") scenario match {
      case "fill-wrong-token" => tokens(otherToken, 10L)
      case "fill-underfilled" => tokens(tokenId, 9L)
      case "fill-overfilled" => tokens(tokenId, 11L)
      case "fill-empty-inventory" => noTokens
      case "fill-extra-inventory" => Array((tokenId, 10L), (otherToken, 1L)).toColl
      case _ => tokens(tokenId, 10L)
    } else noTokens
    val collateral = if (side == "sell" && scenario == "fill-native-overflow")
      Long.MaxValue - 1L else 2000000L
    val self = new ErgoBoxCandidate(collateral, tree, 0, locked)
      .toBox(ErgoBox.allZerosModifierId, 0.toShort)

    val sponsored = scenario.startsWith("sponsor-")
    val fee =
      if (scenario == "fee-too-high" || scenario == "sponsor-fee-too-high") 101L
      else 50L
    val received = 2000000L + (if (sponsored) 500L else 0L) - fee
    val refundTree =
      if (scenario == "redirect" || scenario == "sponsor-redirect") thirdTree
      else ownerTree
    val feeRecipient =
      if (scenario == "wrong-fee-script" || scenario == "sponsor-wrong-fee-script")
        thirdTree else feeTree
    val refundTokens =
      if (side == "buy") noTokens
      else if (scenario == "token-shortfall") tokens(tokenId, 9L)
      else if (scenario == "wrong-token") tokens(otherToken, 10L)
      else locked
    val refund = new ErgoBoxCandidate(received, refundTree, 0, refundTokens)
    val feeOutput = new ErgoBoxCandidate(fee, feeRecipient, 0)
    val sponsorTree = if (scenario == "sponsor-foreign") thirdTree else ownerTree
    val sponsorTokens = if (scenario == "sponsor-token") tokens(tokenId, 1L) else noTokens
    val extra = new ErgoBoxCandidate(500L, sponsorTree, 0, sponsorTokens)
      .toBox(ErgoBox.allZerosModifierId, 1.toShort)
    val third = new ErgoBoxCandidate(50L, ownerTree, 0)
      .toBox(ErgoBox.allZerosModifierId, 2.toShort)
    // A positive SELL fill must not mint native coins from thin air:
    // the buyer adds 1,001,000 to SELF's 2,000,000, matching both outputs.
    val buyerFunding = new ErgoBoxCandidate(1001000L, thirdTree, 0)
      .toBox(ErgoBox.allZerosModifierId, 3.toShort)
    val spending = if (side == "sell" && scenario.startsWith("fill"))
      IndexedSeq(self, buyerFunding)
    else if (!sponsored) IndexedSeq(self)
      else if (scenario == "sponsor-three-inputs") IndexedSeq(self, extra, third)
      else if (scenario == "sponsor-duplicate-self") IndexedSeq(self, self)
      else IndexedSeq(self, extra)
    val original = IndexedSeq(refund, feeOutput)

    val outputs = scenario match {
      case "missing-fee" => IndexedSeq(refund)
      case "unexpected-output" => original :+ new ErgoBoxCandidate(1L, thirdTree, 0)
      case "native-shortfall" | "sponsor-native-shortfall" => IndexedSeq(
        new ErgoBoxCandidate(received - 1L, ownerTree, 0, refundTokens), feeOutput
      )
      case "fill" if side == "buy" =>
        IndexedSeq(new ErgoBoxCandidate(
          1000000L, ownerTree, 0, tokens(tokenId, 100L),
          Map(ErgoBox.R4 -> ByteArrayConstant(self.id))
        ))
      case name if side == "sell" && name.startsWith("fill") =>
        // The old contract accepted 1,000 units even though SELF locked 2M.
        // New sell candidate must give back SELF.value PLUS 1,000 price.
        val payout = if (name == "fill-underpaid-native") 2000999L
          else if (name == "fill-native-overflow") Long.MaxValue
          else 2001000L
        val payoutTokens = if (name == "fill-tokens-in-payout")
          tokens(otherToken, 1L) else noTokens
        IndexedSeq(
          // Transfer the entire locked token inventory to the buyer.
          new ErgoBoxCandidate(1000000L, thirdTree, 0, locked),
          new ErgoBoxCandidate(
            payout, ownerTree, 0, payoutTokens,
            Map(ErgoBox.R4 -> ByteArrayConstant(self.id))
          )
        )
      case _ => original
    }

    val tx = ErgoLikeTransaction(
      spending.map(b => Input(b.id, ProverResult.empty)), outputs
    )
    val empty = CostingSigmaDslBuilder.Colls.emptyColl[Byte]
    val preHeader = CPreHeader(
      0, empty, 3L, 0L, 100,
      CryptoConstants.dlogGroup.generator, empty
    )
    val ctx = new ErgoLikeContext(
      AvlTreeData.dummy, CostingSigmaDslBuilder.Colls.emptyColl[Header],
      preHeader, IndexedSeq.empty, spending, tx, 0,
      ContextExtension.empty, ValidationRules.currentSettings,
      SigmaConstants.ScriptCostLimit.value, 0L, 1.toByte
    )
    (tree, ctx)
  }

  private def authorized(side: String, scenario: String,
                         signer: Option[DLogProverInput]): Boolean = {
    val (tree, ctx) = context(side, scenario)
    implicit val ir: IRContext = new RuntimeIRContext
    val verifier = new ErgoLikeInterpreter { override type CTX = ErgoLikeContext }
    val proof = signer match {
      case None => Some(ProverResult.empty)
      case Some(key) =>
        val prover = new ErgoLikeInterpreter with ProverInterpreter {
          override type CTX = ErgoLikeContext
          override val secrets = Seq(key)
        }
        prover.prove(tree, ctx, msg).toOption
    }
    proof.exists(p => verifier.verify(tree, ctx, p, msg).toOption.exists(_._1))
  }

  private def validateSignedTwoInputTransaction(side: String): Unit = {
    val (tree, unsignedCtx) = context(side, "sponsor-safe")
    unsignedCtx.boxesToSpend.size shouldBe 2
    val originalTx = unsignedCtx.spendingTransaction
    val message = originalTx.messageToSign
    val sponsorCtx = ErgoLikeContext.copy(unsignedCtx)(selfIndex = 1)
    implicit val ir: IRContext = new RuntimeIRContext
    val prover = new ErgoLikeInterpreter with ProverInterpreter {
      override type CTX = ErgoLikeContext
      override val secrets = Seq(ownerSk)
    }
    val verifier = new ErgoLikeInterpreter { override type CTX = ErgoLikeContext }
    val orderProof = prover.prove(tree, unsignedCtx, message).get
    val sponsorProof = prover.prove(sponsorCtx.self.ergoTree, sponsorCtx, message).get
    val signed = ErgoLikeTransaction(
      IndexedSeq(
        Input(unsignedCtx.boxesToSpend(0).id, orderProof),
        Input(unsignedCtx.boxesToSpend(1).id, sponsorProof)
      ), originalTx.outputCandidates
    )
    java.util.Arrays.equals(signed.messageToSign, message) shouldBe true
    val ctxOrderSigned = unsignedCtx.withTransaction(signed)
    val ctxSponsorSigned = sponsorCtx.withTransaction(signed)
    verifier.verify(tree, ctxOrderSigned, orderProof, message).get._1 shouldBe true
    verifier.verify(sponsorCtx.self.ergoTree, ctxSponsorSigned, sponsorProof, message).get._1 shouldBe true

    // Extra invariant checks are a test-fixture assertion. They are NOT
    // chain-level validation or a substitute for a fully validating node.
    unsignedCtx.boxesToSpend.map(_.value).sum shouldBe
      originalTx.outputCandidates.map(_.value).sum
    originalTx.inputs.map(_.boxId).distinct.size shouldBe 2

    // The sponsor input carries its own owner script, and an attacker with
    // a different key cannot create its spending proof.
    val badProver = new ErgoLikeInterpreter with ProverInterpreter {
      override type CTX = ErgoLikeContext
      override val secrets = Seq(thirdSk)
    }
    badProver.prove(sponsorCtx.self.ergoTree, sponsorCtx, message).isFailure shouldBe true

    // An existing proof is cryptographically bound to these tx bytes.
    val altered = ErgoLikeTransaction(
      signed.inputs,
      IndexedSeq(
        new ErgoBoxCandidate(123L, ownerTree, 0),
        originalTx.outputCandidates(1)
      )
    )
    java.util.Arrays.equals(altered.messageToSign, message) shouldBe false
    verifier.verify(sponsorCtx.self.ergoTree, ctxSponsorSigned, sponsorProof,
      altered.messageToSign).toOption.exists(_._1) shouldBe false
  }

  "Two-input signature binding" should "verify BOTH order and sponsor proofs for buy" in {
    validateSignedTwoInputTransaction("buy")
  }
  it should "verify BOTH order and sponsor proofs for sell" in {
    validateSignedTwoInputTransaction("sell")
  }

  "Guarded buy cancellation" should "permit exact owner refund with a real signature" in {
    authorized("buy", "safe", Some(ownerSk)) shouldBe true
  }
  it should "not permit refund without the signature" in {
    authorized("buy", "safe", None) shouldBe false
  }
  it should "reject owner-signed redirect to attacker" in {
    authorized("buy", "redirect", Some(ownerSk)) shouldBe false
  }
  it should "reject owner-signed fee and native conservation violations" in {
    authorized("buy", "fee-too-high", Some(ownerSk)) shouldBe false
    authorized("buy", "native-shortfall", Some(ownerSk)) shouldBe false
  }
  it should "reject unauthorized fee scripts and extra outputs" in {
    authorized("buy", "wrong-fee-script", Some(ownerSk)) shouldBe false
    authorized("buy", "unexpected-output", Some(ownerSk)) shouldBe false
  }
  it should "reject missing fee output and stranger signature" in {
    authorized("buy", "missing-fee", Some(ownerSk)) shouldBe false
    authorized("buy", "safe", Some(thirdSk)) shouldBe false
  }
  it should "preserve unsigned successful fill" in {
    authorized("buy", "fill", None) shouldBe true
  }

  "Guarded sell cancellation" should "permit exact owner refund including locked tokens" in {
    authorized("sell", "safe", Some(ownerSk)) shouldBe true
  }
  it should "reject owner-signed redirect" in {
    authorized("sell", "redirect", Some(ownerSk)) shouldBe false
  }
  it should "reject owner-signed token theft and token substitution" in {
    authorized("sell", "token-shortfall", Some(ownerSk)) shouldBe false
    authorized("sell", "wrong-token", Some(ownerSk)) shouldBe false
  }
  it should "reject excessive fees, wrong fee script and extra outputs" in {
    authorized("sell", "fee-too-high", Some(ownerSk)) shouldBe false
    authorized("sell", "wrong-fee-script", Some(ownerSk)) shouldBe false
    authorized("sell", "unexpected-output", Some(ownerSk)) shouldBe false
  }
  it should "reject stranger signature and unsigned refund" in {
    authorized("sell", "safe", Some(thirdSk)) shouldBe false
    authorized("sell", "safe", None) shouldBe false
  }
  it should "preserve unsigned successful fill" in {
    authorized("sell", "fill", None) shouldBe true
  }

  "Asset-bound sell fill with buyer funding" should "preserve assets and verify both input scripts" in {
    // Closer to a real spend than standalone Sigma predicate checks:
    // two inputs, no implicit token issuance, and buyer's input signed.
    // Still NOT a full node, miner-fee, mempool or consensus validation.
    val (sellTree, unsignedCtx) = context("sell", "fill")
    unsignedCtx.boxesToSpend.size shouldBe 2
    val proposal = unsignedCtx.spendingTransaction
    val message = proposal.messageToSign

    unsignedCtx.boxesToSpend.map(b => BigInt(b.value)).sum shouldBe
      proposal.outputCandidates.map(b => BigInt(b.value)).sum
    // Digest32 wraps Array[Byte]; Array equality may compare references,
    // so canonicalize IDs into value-based vectors before asserting equality.
    unsignedCtx.boxesToSpend.flatMap(b => b.tokens.toArray)
      .map { case (id, count) => (id.toVector, count) } shouldBe
      proposal.outputCandidates.flatMap(b => b.tokens.toArray)
        .map { case (id, count) => (id.toVector, count) }

    implicit val ir: IRContext = new RuntimeIRContext
    val buyerCtx = ErgoLikeContext.copy(unsignedCtx)(selfIndex = 1)
    val buyerProver = new ErgoLikeInterpreter with ProverInterpreter {
      override type CTX = ErgoLikeContext
      override val secrets = Seq(thirdSk)
    }
    val buyerProof = buyerProver.prove(buyerCtx.self.ergoTree, buyerCtx, message).get
    val signed = ErgoLikeTransaction(
      IndexedSeq(
        Input(unsignedCtx.boxesToSpend(0).id, ProverResult.empty),
        Input(unsignedCtx.boxesToSpend(1).id, buyerProof)
      ), proposal.outputCandidates
    )
    java.util.Arrays.equals(signed.messageToSign, message) shouldBe true
    val verifier = new ErgoLikeInterpreter { override type CTX = ErgoLikeContext }
    verifier.verify(sellTree, unsignedCtx.withTransaction(signed),
      ProverResult.empty, message).get._1 shouldBe true
    verifier.verify(buyerCtx.self.ergoTree, buyerCtx.withTransaction(signed),
      buyerProof, message).get._1 shouldBe true
  }

  "Asset-bound sell fill" should "reject wrong token and non-exact inventory" in {
    authorized("sell", "fill-wrong-token", None) shouldBe false
    authorized("sell", "fill-underfilled", None) shouldBe false
    authorized("sell", "fill-overfilled", None) shouldBe false
    authorized("sell", "fill-empty-inventory", None) shouldBe false
    authorized("sell", "fill-extra-inventory", None) shouldBe false
  }
  it should "reject a native payout below box collateral plus sale price" in {
    authorized("sell", "fill-underpaid-native", None) shouldBe false
  }
  it should "reject int64-overflow-priced native collateral" in {
    // BigInt in the script must not wrap SELF.value + MinNativeAmount.
    authorized("sell", "fill-native-overflow", None) shouldBe false
  }
  it should "reject unrelated tokens in seller native payout" in {
    authorized("sell", "fill-tokens-in-payout", None) shouldBe false
  }

  "Sponsored buy cancellation" should "refund locked value and change from owner fee sponsor" in {
    authorized("buy", "sponsor-safe", Some(ownerSk)) shouldBe true
  }
  it should "require the owner's signature" in {
    authorized("buy", "sponsor-safe", None) shouldBe false
  }
  it should "reject a sponsor controlled by a different script" in {
    authorized("buy", "sponsor-foreign", Some(ownerSk)) shouldBe false
  }
  it should "reject sponsor boxes with tokens" in {
    authorized("buy", "sponsor-token", Some(ownerSk)) shouldBe false
  }
  it should "reject stolen refund and prohibited fees" in {
    authorized("buy", "sponsor-redirect", Some(ownerSk)) shouldBe false
    authorized("buy", "sponsor-fee-too-high", Some(ownerSk)) shouldBe false
    authorized("buy", "sponsor-wrong-fee-script", Some(ownerSk)) shouldBe false
  }
  it should "reject native deficit and an unexpected third input" in {
    authorized("buy", "sponsor-native-shortfall", Some(ownerSk)) shouldBe false
    authorized("buy", "sponsor-three-inputs", Some(ownerSk)) shouldBe false
  }
  it should "reject a duplicate SELF as sponsor" in {
    authorized("buy", "sponsor-duplicate-self", Some(ownerSk)) shouldBe false
  }

  "Sponsored sell cancellation" should "refund all locked tokens and native using extra owner fee box" in {
    authorized("sell", "sponsor-safe", Some(ownerSk)) shouldBe true
  }
  it should "reject sponsor with assets, another owner's script and extra inputs" in {
    authorized("sell", "sponsor-token", Some(ownerSk)) shouldBe false
    authorized("sell", "sponsor-foreign", Some(ownerSk)) shouldBe false
    authorized("sell", "sponsor-three-inputs", Some(ownerSk)) shouldBe false
  }
  it should "reject tampered recipient, native conservation and fees" in {
    authorized("sell", "sponsor-redirect", Some(ownerSk)) shouldBe false
    authorized("sell", "sponsor-native-shortfall", Some(ownerSk)) shouldBe false
    authorized("sell", "sponsor-fee-too-high", Some(ownerSk)) shouldBe false
  }

}
