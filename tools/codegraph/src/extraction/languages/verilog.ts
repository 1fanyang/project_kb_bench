import type { Node as SyntaxNode } from 'web-tree-sitter';
import { getNodeText } from '../tree-sitter-helpers';
import type { LanguageExtractor } from '../tree-sitter-types';

/**
 * Find the first `simple_identifier` descendant in BFS order.
 * tree-sitter-verilog rarely uses named fields, so for most node kinds the
 * name is "the first identifier child somewhere inside the header".
 *
 * Walk depth is capped to avoid descending into a body that happens to use
 * an identifier early (function body's first ref vs. function's name).
 */
function firstIdentifier(node: SyntaxNode, maxDepth = 4): SyntaxNode | undefined {
  const queue: Array<{ n: SyntaxNode; d: number }> = [{ n: node, d: 0 }];
  while (queue.length) {
    const { n, d } = queue.shift()!;
    if (n !== node && n.type === 'simple_identifier') return n;
    if (d >= maxDepth) continue;
    for (let i = 0; i < n.namedChildCount; i++) {
      const c = n.namedChild(i);
      if (c) queue.push({ n: c, d: d + 1 });
    }
  }
  return undefined;
}

function resolveVerilogName(node: SyntaxNode, source: string): string | undefined {
  // module_declaration > module_header > simple_identifier
  if (node.type === 'module_declaration') {
    const header = node.namedChildren.find((c) => c?.type === 'module_header');
    if (header) {
      const id = firstIdentifier(header, 2);
      if (id) return getNodeText(id, source);
    }
  }
  // module_instantiation / checker_instantiation / udp_instantiation:
  // the target module name comes first, instance name second. For "calls"
  // edges we want the *target* (which the framework reads as the node's
  // own "name" before remapping). The first identifier descendant is the
  // target identifier.
  if (
    node.type === 'module_instantiation' ||
    node.type === 'checker_instantiation' ||
    node.type === 'udp_instantiation'
  ) {
    const id = firstIdentifier(node, 3);
    if (id) return getNodeText(id, source);
  }
  // For everything else (function_declaration, task_declaration, class_declaration,
  // package_declaration, interface_declaration, parameter_declaration, …), the
  // first simple_identifier descendant within ~4 levels is the declared name.
  const id = firstIdentifier(node, 4);
  if (id) return getNodeText(id, source);
  return undefined;
}

/**
 * Verilog / SystemVerilog extractor.
 *
 * Node-type names verified against tree-sitter-verilog v1.0.3 in Phase 0 of
 * the kb_benchmark analyzer-v2 work; see _observed_node_kinds.md in the
 * consuming project. Key quirks worth knowing before editing:
 *
 * - if / else uses `conditional_statement`, NOT `if_statement`.
 * - always blocks use `always_construct` (covers `always`, `always_ff`,
 *   `always_comb`, `always_latch`).
 * - module instances disambiguate ambiguously: `child #(.W(8)) u(...)` parses
 *   as `module_instantiation`, `child u(.clk(clk))` as `checker_instantiation`,
 *   and `child u(clk, rst)` as `udp_instantiation`. We list all three as
 *   callTypes so every instance produces a `calls` edge to the instantiated
 *   module/UDP/checker name; downstream resolution can disambiguate by what
 *   the target identifier resolves to.
 *
 * The framework only has `classTypes` (no `moduleTypes`/`namespaceTypes`), so
 * module_declaration / package_declaration / class_declaration all surface as
 * NodeKind `class`. Downstream consumers that need to distinguish "Verilog
 * module" from "C++ class" key on `language === 'verilog'` AND on the source
 * file extension.
 */
export const verilogExtractor: LanguageExtractor = {
  functionTypes: ['function_declaration', 'task_declaration'],
  classTypes: [
    'module_declaration',
    'package_declaration',
    'class_declaration',
  ],
  methodTypes: ['function_declaration', 'task_declaration'],
  interfaceTypes: ['interface_declaration'],
  structTypes: [],
  enumTypes: [],
  typeAliasTypes: [],
  importTypes: ['include_directive', 'package_import_declaration'],
  callTypes: ['subroutine_call'],
  // Module / UDP / checker instantiation — disambiguated only by the grammar
  // based on syntax shape. All three forms produce an `instantiates` edge
  // from the enclosing module/class to the named target.
  instantiationTypes: [
    'module_instantiation',
    'checker_instantiation',
    'udp_instantiation',
  ],
  variableTypes: [
    'parameter_declaration',
    'net_declaration',
    'data_declaration',
  ],
  nameField: 'name',
  bodyField: 'body',
  paramsField: 'parameters',
  returnField: 'return_type',
  resolveName: resolveVerilogName,
  getSignature: () => undefined,
};
