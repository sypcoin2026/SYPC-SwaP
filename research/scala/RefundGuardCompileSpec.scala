package io.ergodex.core

import org.scalatest.flatspec.AnyFlatSpec
import org.scalatest.matchers.should.Matchers
import sigmastate.basics.DLogProtocol.DLogProverInput
import sigmastate.serialization.ErgoTreeSerializer
import sigmastate.Values.{ErgoTree, SigmaPropConstant}

/** Research-only: compile variants, NOT blockchain validation or an audit. */
class RefundGuardCompileSpec extends AnyFlatSpec with Matchers {
  private val owner = DLogProverInput(BigInt(123456789).bigInteger).publicImage
  private val fee = DLogProverInput(BigInt(987654321).bigInteger).publicImage
  private val feeScript = ErgoTree.fromProposition(SigmaPropConstant(fee)).bytes

  private def bytes(side: String, maxFee: Long, feeBytes: Array[Byte]): Array[Byte] = {
    val isolated = new SigmaPlatform {}
    val src = isolated.readSource(
      if (side == "buy") "research/ergo_script/AtomicBuyRefundGuard.sc"
      else "research/ergo_script/AtomicSellRefundGuard.sc"
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
        "MinNativeAmount" -> 1000L,
        "MaxCancelFee" -> maxFee,
        "FeePropBytes" -> feeBytes
      )
    ErgoTreeSerializer.DefaultSerializer.serializeErgoTree(isolated.compile(src, env))
  }

  "Refund-guard buy candidate" should "compile reproducibly in fresh compilers" in {
    val b = bytes("buy", 500L, feeScript)
    b.length should be > 0
    (1 to 3).foreach { _ => b.toSeq shouldBe bytes("buy", 500L, feeScript).toSeq }
  }
  it should "bind exact fee limit and fee script bytes" in {
    bytes("buy", 500L, feeScript).toSeq should not be bytes("buy", 501L, feeScript).toSeq
    bytes("buy", 500L, feeScript).toSeq should not be bytes("buy", 500L, Array.fill[Byte](33)(3)).toSeq
  }

  "Refund-guard sell candidate" should "compile reproducibly in fresh compilers" in {
    val b = bytes("sell", 500L, feeScript)
    b.length should be > 0
    (1 to 3).foreach { _ => b.toSeq shouldBe bytes("sell", 500L, feeScript).toSeq }
  }
  it should "bind exact fee limit and fee script bytes" in {
    bytes("sell", 500L, feeScript).toSeq should not be bytes("sell", 501L, feeScript).toSeq
    bytes("sell", 500L, feeScript).toSeq should not be bytes("sell", 500L, Array.fill[Byte](33)(3)).toSeq
  }
}
