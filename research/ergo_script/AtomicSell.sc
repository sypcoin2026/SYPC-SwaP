// SYPC Swap laboratory ONLY. NOT deployed, not tested on SYPC.
// Adapted from ergoplatform/ergo-contracts AssetsAtomicExchange.scala
// @ 17ed58b39460e5520de56f615936d918603a3b9e (CC0-1.0).
// Owner signature overrides the fill check (source cancellation semantics).
{
  val validFill =
    OUTPUTS.size > 1 &&
    OUTPUTS(1).R4[Coll[Byte]].isDefined &&
    OUTPUTS(1).R4[Coll[Byte]].get == SELF.id &&
    OUTPUTS(1).value >= MinNativeAmount &&
    OUTPUTS(1).propositionBytes == SellerPk.propBytes
  sigmaProp(SellerPk || validFill)
}
