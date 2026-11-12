package io.ergodex.core

import org.scalatest.flatspec.AnyFlatSpec
import org.scalatest.matchers.should.Matchers
import sigmastate.basics.DLogProtocol.DLogProverInput
import sigmastate.serialization.ErgoTreeSerializer

// This compiles candidate ErgoScript against Spectrum's pinned Sigma 4.0.5
// only. This is NOT an execution test on the SYPC consensus interpreter,
// formal verification, signature check, or authorization for use of funds.
class AtomicScriptCompileSpec extends AnyFlatSpec with Matchers with SigmaPlatform {
  private val buyerPk = DLogProverInput(BigInt(123456789).bigInteger).publicImage
  private val sellerPk = DLogProverInput(BigInt(987654321).bigInteger).publicImage

  private def serialize(source: String, env: Map[String, Any]): Array[Byte] = {
    val tree = compile(readSource(source), env)
    ErgoTreeSerializer.DefaultSerializer.serializeErgoTree(tree)
  }

  "AtomicBuy port candidate" should "compile deterministically into ErgoTree" in {
    val env: Map[String, Any] = Map(
      "BuyerPk" -> buyerPk,
      "TokenId" -> Array.fill[Byte](32)(12),
      "MinTokenAmount" -> 100L
    )
    val source = "research/ergo_script/AtomicBuy.sc"
    val first = serialize(source, env)
    first.length should be > 0
    first.toSeq shouldBe serialize(source, env).toSeq
  }

  it should "bind the requested token and minimum amount in its compiled tree" in {
    val source = "research/ergo_script/AtomicBuy.sc"
    val a = serialize(source, Map(
      "BuyerPk" -> buyerPk,
      "TokenId" -> Array.fill[Byte](32)(12),
      "MinTokenAmount" -> 100L
    ))
    val b = serialize(source, Map(
      "BuyerPk" -> buyerPk,
      "TokenId" -> Array.fill[Byte](32)(13),
      "MinTokenAmount" -> 101L
    ))
    a.toSeq should not be b.toSeq
  }

  "AtomicSell port candidate" should "compile deterministically into ErgoTree" in {
    val env: Map[String, Any] = Map(
      "SellerPk" -> sellerPk,
      "MinNativeAmount" -> 999L
    )
    val source = "research/ergo_script/AtomicSell.sc"
    val first = serialize(source, env)
    first.length should be > 0
    first.toSeq shouldBe serialize(source, env).toSeq
  }

  it should "bind seller payout amount in the compiled tree" in {
    val source = "research/ergo_script/AtomicSell.sc"
    val a = serialize(source, Map("SellerPk" -> sellerPk, "MinNativeAmount" -> 999L))
    val b = serialize(source, Map("SellerPk" -> sellerPk, "MinNativeAmount" -> 1000L))
    a.toSeq should not be b.toSeq
  }
}
