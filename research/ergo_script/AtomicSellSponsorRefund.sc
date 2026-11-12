// Research-only, Sigma 4.0.5. NEVER deploy without SYPC tests and an audit.
// Alternative to AtomicSellRefundGuard: owner may add ONE extra native-only
// UTXO under the same owner's script to sponsor the fee and preserve SELF value.
// Adapted from Ergo Contracts AssetsAtomicExchange (CC0-1.0)
// 17ed58b39460e5520de56f615936d918603a3b9e.
{
  val validFill =
    OUTPUTS.size > 1 &&
    OUTPUTS(1).R4[Coll[Byte]].isDefined &&
    OUTPUTS(1).R4[Coll[Byte]].get == SELF.id &&
    OUTPUTS(1).value >= MinNativeAmount &&
    OUTPUTS(1).propositionBytes == SellerPk.propBytes

  val safeCancel =
    (INPUTS.size == 1 || INPUTS.size == 2) &&
    OUTPUTS.size == 2 &&
    INPUTS(0).id == SELF.id && {
      val refund = OUTPUTS(0)
      val fee = OUTPUTS(1)

      val sponsorAllowed =
        if (INPUTS.size == 1) true
        else {
          val extra = INPUTS(1)
          extra.id != SELF.id &&
          extra.tokens.size == 0 &&
          extra.propositionBytes == SellerPk.propBytes
        }
      val sponsorValue =
        if (INPUTS.size == 2) INPUTS(1).value.toBigInt
        else 0.toBigInt

      val correctNative =
        refund.value > 0L &&
        fee.value > 0L &&
        fee.value <= MaxCancelFee &&
        refund.value.toBigInt + fee.value.toBigInt ==
          SELF.value.toBigInt + sponsorValue

      val fullOwnRefund =
        if (INPUTS.size == 2) refund.value.toBigInt >= SELF.value.toBigInt
        else true

      sponsorAllowed &&
      correctNative &&
      fullOwnRefund &&
      refund.propositionBytes == SellerPk.propBytes &&
      fee.propositionBytes == FeePropBytes &&
      refund.tokens == SELF.tokens &&
      fee.tokens.size == 0
    }

  sigmaProp((SellerPk && safeCancel) || validFill)
}
