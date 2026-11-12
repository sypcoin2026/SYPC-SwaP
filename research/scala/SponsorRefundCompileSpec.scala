package io.ergodex.core

import org.scalatest.flatspec.AnyFlatSpec
import org.scalatest.matchers.should.Matchers
import sigmastate.basics.DLogProtocol.DLogProverInput
import sigmastate.serialization.ErgoTreeSerializer
import sigmastate.Values.{ErgoTree, SigmaPropConstant}

/** Research-only: compile variants, NOT blockchain validation or an audit. */
class SponsorRefundCompileSpec extends AnyFlatSpec with Matchers {
  private val owner = DLogProverInput(BigInt(123456789).bigInteger).publicImage
  private val fee = DLogProverInput(BigInt(987654321).bigInteger).publicImage
  private val feeScript = ErgoTree.fromProposition(SigmaPropConstant(fee)).bytes

  private def bytes(
    side: String, maxFee: Long, feeBytes: Array[Byte],
    sellTokenId: Array[Byte] = Array.fill[Byte](32)(12),
    sellTokenAmount: Long = 10L,
    minNativeAmount: Long = 1000L
  ): Array[Byte] = {
    val isolated = new SigmaPlatform {}
    val src = isolated.readSource(
      if (side == "buy") "research/ergo_script/AtomicBuySponsorRefund.sc"
      else "research/ergo_script/AtomicSellSponsorRefund.sc"
    )
    val env: Map[String, Any] =
      if (side == "buy") Map(
        "BuyerPk" -> owner,
        "TokenId" -> Array.fill[Byte](32)(12),
        "MinTokenAmount" -> 100L,
        "MaxCancelFee" -> maxFee,
        "FeePropBytes" -> feeBytes
      )
      else Map(
        "SellerPk" -> owner,
        "SellTokenId" -> sellTokenId,
        "SellTokenAmount" -> sellTokenAmount,
        "MinNativeAmount" -> minNativeAmount,
        "MaxCancelFee" -> maxFee,
        "FeePropBytes" -> feeBytes
      )
    ErgoTreeSerializer.DefaultSerializer.serializeErgoTree(isolated.compile(src, env))
  }

  "Sponsor refund buy candidate" should "compile reproducibly in fresh compilers" in {
    val b = bytes("buy", 500L, feeScript)
    b.length should be > 0
    (1 to 3).foreach { _ => b.toSeq shouldBe bytes("buy", 500L, feeScript).toSeq }
  }
  it should "bind exact fee limit and fee script bytes" in {
    bytes("buy", 500L, feeScript).toSeq should not be bytes("buy", 501L, feeScript).toSeq
    bytes("buy", 500L, feeScript).toSeq should not be bytes("buy", 500L, Array.fill[Byte](33)(3)).toSeq
  }

  "Sponsor refund sell asset binding" should "bind token ID, exact amount and native price" in {
    val standard = bytes("sell", 500L, feeScript)
    standard.toSeq should not be bytes(
      "sell", 500L, feeScript, sellTokenId = Array.fill[Byte](32)(13)
    ).toSeq
    standard.toSeq should not be bytes(
      "sell", 500L, feeScript, sellTokenAmount = 11L
    ).toSeq
    standard.toSeq should not be bytes(
      "sell", 500L, feeScript, minNativeAmount = 1001L
    ).toSeq
  }

  "Sponsor refund sell candidate" should "compile reproducibly in fresh compilers" in {
    val b = bytes("sell", 500L, feeScript)
    b.length should be > 0
    (1 to 3).foreach { _ => b.toSeq shouldBe bytes("sell", 500L, feeScript).toSeq }
  }
  it should "bind exact fee limit and fee script bytes" in {
    bytes("sell", 500L, feeScript).toSeq should not be bytes("sell", 501L, feeScript).toSeq
    bytes("sell", 500L, feeScript).toSeq should not be bytes("sell", 500L, Array.fill[Byte](33)(3)).toSeq
  }
}
