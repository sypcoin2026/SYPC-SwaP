// EXPERIMENTAL research only: do not deploy, no SYPC consensus validation.
// Builds on Ergo Contracts AssetsAtomicExchange.scala (CC0-1.0)
// Commit 17ed58b39460e5520de56f615936d918603a3b9e.
// Owner cancellation adds an on-chain exact refund and fee guard.
// Limit: 1-input cancellation can fail for low-native-value boxes; must be resolved.
{
  val validFill =
    OUTPUTS.size > 1 &&
    OUTPUTS(1).R4[Coll[Byte]].isDefined &&
    OUTPUTS(1).R4[Coll[Byte]].get == SELF.id &&
    OUTPUTS(1).value >= MinNativeAmount &&
    OUTPUTS(1).propositionBytes == SellerPk.propBytes

  val safeCancel = INPUTS.size == 1 && OUTPUTS.size == 2 && {
    val refund = OUTPUTS(0)
    val fee = OUTPUTS(1)
    val exactTokens = refund.tokens == SELF.tokens && fee.tokens.size == 0
    val exactNative =
      refund.value > 0L &&
      fee.value > 0L &&
      fee.value <= MaxCancelFee &&
      refund.value.toBigInt + fee.value.toBigInt == SELF.value.toBigInt
    refund.propositionBytes == SellerPk.propBytes &&
    fee.propositionBytes == FeePropBytes &&
    exactTokens &&
    exactNative
  }

  sigmaProp((SellerPk && safeCancel) || validFill)
}
