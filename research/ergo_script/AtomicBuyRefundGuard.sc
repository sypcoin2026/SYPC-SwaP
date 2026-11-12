// EXPERIMENTAL research only: do not deploy, no SYPC consensus validation.
// Builds on Ergo Contracts AssetsAtomicExchange.scala (CC0-1.0)
// Commit 17ed58b39460e5520de56f615936d918603a3b9e.
// Owner cancellation adds an on-chain *refund guard* to the original owner-signature branch.
// Trade fulfillment branch is preserved for comparison.
// Limit: cancellation deliberately requires one input; may strand low-value UTXOs.
// Requires independent liveness, dust, minimum-box and fee validation before deployment.
{
  val validFill =
    OUTPUTS.size > 0 &&
    OUTPUTS(0).R4[Coll[Byte]].isDefined &&
    OUTPUTS(0).tokens.size > 0 &&
    OUTPUTS(0).tokens(0)._1 == TokenId &&
    OUTPUTS(0).tokens(0)._2 >= MinTokenAmount &&
    OUTPUTS(0).R4[Coll[Byte]].get == SELF.id &&
    OUTPUTS(0).propositionBytes == BuyerPk.propBytes

  val safeCancel = INPUTS.size == 1 && OUTPUTS.size == 2 && {
    val refund = OUTPUTS(0)
    val fee = OUTPUTS(1)
    val exactTokens = refund.tokens == SELF.tokens && fee.tokens.size == 0
    val exactNative =
      refund.value > 0L &&
      fee.value > 0L &&
      fee.value <= MaxCancelFee &&
      refund.value.toBigInt + fee.value.toBigInt == SELF.value.toBigInt
    refund.propositionBytes == BuyerPk.propBytes &&
    fee.propositionBytes == FeePropBytes &&
    exactTokens &&
    exactNative
  }

  sigmaProp((BuyerPk && safeCancel) || validFill)
}
