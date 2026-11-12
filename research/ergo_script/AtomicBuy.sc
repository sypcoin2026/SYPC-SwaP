// SYPC Swap laboratory ONLY. NOT deployed, not tested on SYPC.
// Adapted from ergoplatform/ergo-contracts AssetsAtomicExchange.scala
// @ 17ed58b39460e5520de56f615936d918603a3b9e (CC0-1.0).
// Owner signature overrides the fill check (source cancellation semantics).
{
  val validFill =
    OUTPUTS.size > 0 &&
    OUTPUTS(0).R4[Coll[Byte]].isDefined &&
    OUTPUTS(0).tokens.size > 0 &&
    OUTPUTS(0).tokens(0)._1 == TokenId &&
    OUTPUTS(0).tokens(0)._2 >= MinTokenAmount &&
    OUTPUTS(0).R4[Coll[Byte]].get == SELF.id &&
    OUTPUTS(0).propositionBytes == BuyerPk.propBytes
  sigmaProp(BuyerPk || validFill)
}
