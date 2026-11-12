// Research-only, Sigma 4.0.5. NEVER deploy without SYPC tests and an audit.
// Alternative to AtomicBuyRefundGuard: owner may add ONE extra native-only
// UTXO under the same owner's script to sponsor the fee and preserve SELF value.
// Adapted from Ergo Contracts AssetsAtomicExchange (CC0-1.0)
// 17ed58b39460e5520de56f615936d918603a3b9e.
{
  val validFill =
    OUTPUTS.size > 0 &&
    OUTPUTS(0).R4[Coll[Byte]].isDefined &&
    OUTPUTS(0).tokens.size > 0 &&
    OUTPUTS(0).tokens(0)._1 == TokenId &&
    OUTPUTS(0).tokens(0)._2 >= MinTokenAmount &&
    OUTPUTS(0).R4[Coll[Byte]].get == SELF.id &&
    OUTPUTS(0).propositionBytes == BuyerPk.propBytes

  // Avoid INPUTS(1) indexing when an optional sponsor is absent.
  // Using a filtered collection also keeps the normal fill path evaluable.
  val otherInputs = INPUTS.filter { (b: Box) => b.id != SELF.id }
  val sponsorsValid =
    otherInputs.size <= 1 &&
    INPUTS.size == otherInputs.size + 1 &&
    otherInputs.forall { (b: Box) =>
      b.tokens.size == 0 &&
      b.propositionBytes == BuyerPk.propBytes
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
      refund.propositionBytes == BuyerPk.propBytes &&
      fee.propositionBytes == FeePropBytes &&
      refund.tokens == SELF.tokens &&
      fee.tokens.size == 0
    }

  sigmaProp((BuyerPk && safeCancel) || validFill)
}
