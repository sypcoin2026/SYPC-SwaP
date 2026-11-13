ThisBuild / scalaVersion := "2.12.20"
ThisBuild / version := "0.0.0-audit"
ThisBuild / organization := "org.sypcoin.research"

lazy val root = (project in file(".")).settings(
  name := "sypc-swap-sigma607-compile-only",
  libraryDependencies += "org.scorexfoundation" %% "sigma-state" % "6.0.7",
  Compile / run / fork := true,
  Compile / run / javaOptions ++= Seq("-Xms128m", "-Xmx1536m")
)
