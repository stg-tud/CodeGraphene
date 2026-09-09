// Real interprocedural, path-sensitive dataflow query, using Joern's own
// dataflowengineoss (reachableByFlows) -- not the statically exported
// REACHING_DEF/CDG edges, which are intraprocedular only and cannot
// represent a flow that crosses a function-call boundary.
//
// Invoked via: joern --script reachable_by_flows.sc \
//   --param cpgPath=<path> --param sourcePattern=<regex> --param sinkPattern=<regex>
//
// Params are passed as real method arguments (not string-interpolated into
// this script), so arbitrary user-supplied regexes carry no script-injection
// risk.
//
// Output is a simple line-oriented format meant to be parsed by
// codegraphene.taint.joern_query._parse_flows:
//   NUM_FLOWS=<n>
//   FLOW_START
//   ELEM|<code with newlines collapsed to spaces>|<line number, or -1>
//   ...
//   FLOW_END
//   (repeated once per flow)

@main def main(cpgPath: String, sourcePattern: String, sinkPattern: String) = {
  importCpg(cpgPath)

  val source = cpg.parameter.name(sourcePattern)
  val sink = cpg.call.name(sinkPattern).argument
  val flows = sink.reachableByFlows(source)

  println(s"NUM_FLOWS=${flows.size}")
  flows.foreach { flow =>
    println("FLOW_START")
    flow.elements.foreach { e =>
      val code = e.code.replace("\n", " ").replace("\r", "")
      val line = e.lineNumber.getOrElse(-1)
      println(s"ELEM|$code|$line")
    }
    println("FLOW_END")
  }
}
