package org.sypcoin.swap

import java.nio.charset.StandardCharsets.UTF_8
import java.nio.file.{Files, Path, Paths}
import java.security.MessageDigest

import sigmastate.crypto.DLogProtocol.DLogProverInput
import sigma.ast.{ErgoTree, SigmaPropConstant}
import sigma.ast.syntax._
import sigma.compiler.SigmaCompiler
import sigma.compiler.ir.CompiletimeIRContext
import sigma.serialization.ErgoTreeSerializer

import scala.util.Try

/** Compile-only migration gate for six experimental SYPC Swap ErgoScripts.
  *
  * Uses the same sigma-state 6.0.7 artifact declared by SYPC Core build.sbt,
  * but DOES NOT run SYPC's node consensus, UTXO, signatures or a chain.
  * The older Sigma 4.0.5 fingerprints must NEVER be reused as native proofs.
  *
  * Command: sbt -batch "runMain org.sypcoin.swap.NativeSigma607Compile /repo/research/ergo_script"
  */
object NativeSigma607Compile {
  private val ScriptNames = Vector(
    "AtomicBuy.sc", "AtomicSell.sc",
    "AtomicBuyRefundGuard.sc", "AtomicSellRefundGuard.sc",
    "AtomicBuySponsorRefund.sc", "AtomicSellSponsorRefund.sc"
  )

  private def sha256(data: Array[Byte]): String =
    MessageDigest.getInstance("SHA-256").digest(data)
      .map(b => f"${b & 0xff}%02x").mkString

  private def script(path: Path): String = {
    require(Files.isRegularFile(path) && !Files.isSymbolicLink(path),
      "SYPC_NATIVE6_SOURCE_NOT_REGULAR")
    val bytes = Files.readAllBytes(path)
    require(bytes.length > 100 && bytes.length <= 16384,
      "SYPC_NATIVE6_SOURCE_SIZE_INVALID")
    new String(bytes, UTF_8)
  }

  private def compile(src: String, env: Map[String, Any]): Array[Byte] = {
    // A fresh IR context and compiler avoid process-global compiler-test state.
    implicit val ir: CompiletimeIRContext = new CompiletimeIRContext
    val result = SigmaCompiler(0x30.toByte).compile(env, src)
    val tree = ErgoTree.fromProposition(result.buildTree.asSigmaProp)
    val bytes = tree.bytes
    val restored = ErgoTreeSerializer.DefaultSerializer.deserializeErgoTree(bytes)
    require(restored.bytes.sameElements(bytes), "SYPC_NATIVE6_SERIALIZATION_FAILED")
    require(bytes.length > 5, "SYPC_NATIVE6_EMPTY_TREE")
    bytes
  }

  def main(args: Array[String]): Unit = {
    require(args.length == 1, "SYPC_NATIVE6_SOURCE_ROOT_REQUIRED")
    val directory = Paths.get(args(0)).toRealPath()
    require(Files.isDirectory(directory), "SYPC_NATIVE6_SOURCE_DIR_REQUIRED")

    // Pin the *actual loaded class* to the exact 6.0.7 jar, not merely the
    // build.sbt version string (which can be overridden in other projects).
    val origin = Option(classOf[SigmaCompiler].getProtectionDomain)
      .flatMap(p => Option(p.getCodeSource)).map(_.getLocation.toURI)
      .map(uri => Paths.get(uri).getFileName.toString)
      .getOrElse(throw new IllegalStateException("SYPC_NATIVE6_JAR_ORIGIN_UNAVAILABLE"))
    require(origin == "sigma-state_2.12-6.0.7.jar",
      "SYPC_NATIVE6_WRONG_RUNTIME_JAR")

    val owner = DLogProverInput(BigInt(123456789).bigInteger).publicImage
    val fee = DLogProverInput(BigInt(987654321).bigInteger).publicImage
    val feeScript = ErgoTree.fromProposition(SigmaPropConstant(fee)).bytes
    val common = Map[String, Any](
      "MaxCancelFee" -> 500L,
      "FeePropBytes" -> feeScript
    )
    def vars(name: String): Map[String, Any] = {
      val buy = name.startsWith("AtomicBuy")
      val versioned = name.contains("RefundGuard") || name.contains("SponsorRefund")
      val side = if (buy) Map[String, Any](
        "BuyerPk" -> owner, "TokenId" -> Array.fill[Byte](32)(12),
        "MinTokenAmount" -> 100L
      ) else Map[String, Any](
        "SellerPk" -> owner, "MinNativeAmount" -> 1000L
      ) ++ (if (name.contains("SponsorRefund"))
        Map[String, Any](
          "SellTokenId" -> Array.fill[Byte](32)(12),
          "SellTokenAmount" -> 10L
        )
      else Map.empty[String, Any])
      if (versioned) side ++ common else side
    }

    ScriptNames.foreach { name =>
      val source = script(directory.resolve(name))
      val env = vars(name)
      val initial = compile(source, env)
      val repeat = compile(source, env)
      require(initial.sameElements(repeat),
        "SYPC_NATIVE6_NONDETERMINISTIC_ERGOTREE:" + name)
      val key = if (name.startsWith("AtomicBuy")) "MinTokenAmount"
        else "MinNativeAmount"
      val changed = env.updated(key, env(key).asInstanceOf[Long] + 1L)
      val mutated = compile(source, changed)
      require(!initial.sameElements(mutated),
        "SYPC_NATIVE6_CONTRACT_PARAMETER_NOT_BOUND:" + name)
      println(s"SYPC_NATIVE6_COMPILE_PASS ${name} sha256=${sha256(initial)} bytes=${initial.length}")
    }
    val malformed = Try(compile("{ val broken = !!OUTPUTS( }", Map.empty[String, Any]))
    require(malformed.isFailure, "SYPC_NATIVE6_MALFORMED_SCRIPT_ACCEPTED")
    println("SYPC_NATIVE6_COMPILER_ONLY_SIX_CONTRACTS_PASS")
    println("NOT_SYPC_CONSENSUS_NOT_FULL_TRANSACTION_NOT_SIGNATURE_VERIFICATION")
  }
}
