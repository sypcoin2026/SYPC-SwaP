// Research-only, Sigma 4.0.5. NEVER deploy without SYPC tests and an audit.
// Alternative to AtomicSellRefundGuard: owner may add ONE extra native-only
// UTXO under the same owner's script to sponsor the fee and preserve SELF value.
// Adapted from Ergo Contracts AssetsAtomicExchange (CC0-1.0)
// 17ed58b39460e5520de56f615936d918603a3b9e.
{
  // A signed-free fill must never sell a different token, extra assets, or
  // more tokens than the order specifies. Recover the box's own native value
  // ON TOP of the seller's required sale price; no implicit native subsidy.
  // All parameters are baked into the ErgoTree at order creation.
  val validFill =
    MinNativeAmount > 0L &&
    SellTokenAmount > 0L &&
    SELF.tokens.size == 1 &&
    SELF.tokens(0)._1 == SellTokenId &&
    SELF.tokens(0)._2 == SellTokenAmount &&
    OUTPUTS.size > 1 &&
    OUTPUTS(1).R4[Coll[Byte]].isDefined &&
    OUTPUTS(1).R4[Coll[Byte]].get == SELF.id &&
    OUTPUTS(1).value.toBigInt >=
      SELF.value.toBigInt + MinNativeAmount.toBigInt &&
    OUTPUTS(1).tokens.size == 0 &&
    OUTPUTS(1).propositionBytes == SellerPk.propBytes

  // Avoid INPUTS(1) indexing when an optional sponsor is absent.
  // Using a filtered collection also keeps the normal fill path evaluable.
  val otherInputs = INPUTS.filter { (b: Box) => b.id != SELF.id }
  val sponsorsValid =
    otherInputs.size <= 1 &&
    INPUTS.size == otherInputs.size + 1 &&
    otherInputs.forall { (b: Box) =>
      b.tokens.size == 0 &&
      b.propositionBytes == SellerPk.propBytes
    }
  val extraNative = otherInputs.fold(0.toBigInt, { (sum: BigInt, b: Box) =>
    sum + b.value.toBigInt
  })

  val safeCancel =
    INPUTS.size > 0 &&
    INPUTS(0).id == SELF.id &&
    OUTPUTS.size == 2 && {
      val refund = OUTPUTS(0)
      val fee = OUTPUTS(1)
      val nativeConserved =
        refund.value > 0L &&
        fee.value > 0L &&
        fee.value <= MaxCancelFee &&
        refund.value.toBigInt + fee.value.toBigInt ==
          SELF.value.toBigInt + extraNative
      val fullOwnRefund =
        if (otherInputs.size == 1)
          refund.value.toBigInt >= SELF.value.toBigInt
        else true

      sponsorsValid &&
      nativeConserved &&
      fullOwnRefund &&
      refund.propositionBytes == SellerPk.propBytes &&
      fee.propositionBytes == FeePropBytes &&
      refund.tokens == SELF.tokens &&
      fee.tokens.size == 0
    }

  sigmaProp((SellerPk && safeCancel) || validFill)
}
