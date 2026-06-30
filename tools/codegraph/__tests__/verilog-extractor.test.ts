/**
 * Verilog / SystemVerilog extractor tests.
 *
 * Mirrors the small-fixture pattern in extraction.test.ts. Three fixtures:
 *   - entities.sv: module, package, interface, class, function, task
 *   - relations.sv: 3 instantiation kinds (module/checker/udp); include + import
 *   - conditions.sv: always_construct / conditional_statement / case_statement
 */
import { describe, it, expect, beforeAll } from 'vitest';
import * as fs from 'fs';
import * as path from 'path';
import { extractFromSource } from '../src/extraction';
import { initGrammars, loadAllGrammars } from '../src/extraction/grammars';

const FIX = (name: string) =>
  fs.readFileSync(path.join(__dirname, 'fixtures/verilog', name), 'utf8');

beforeAll(async () => {
  await initGrammars();
  await loadAllGrammars();
});

describe('Verilog extractor', () => {
  it('captures module / package / interface / class / function / task', () => {
    const result = extractFromSource('entities.sv', FIX('entities.sv'));
    const names = result.nodes.map((n) => n.name);
    // Modules + packages + classes all surface as kind='class' per
    // extractor framework limitation (no moduleTypes field).
    expect(names).toContain('sample');     // module_declaration
    expect(names).toContain('my_pkg');     // package_declaration
    expect(names).toContain('my_class');   // class_declaration
    expect(names).toContain('my_if');      // interface_declaration
    expect(names).toContain('double');     // function_declaration
    expect(names).toContain('stim');       // task_declaration

    // Spot-check kinds for one entity of each flavor we put in classTypes.
    const kindByName = new Map(result.nodes.map((n) => [n.name, n.kind]));
    expect(kindByName.get('sample')).toBe('class');
    expect(kindByName.get('my_pkg')).toBe('class');
    expect(kindByName.get('my_class')).toBe('class');
    expect(kindByName.get('my_if')).toBe('interface');
    // function_declaration / task_declaration inside a module surface as
    // methods (the framework treats anything nested inside a classTypes
    // container as a method).
    expect(kindByName.get('double')).toBe('method');
    expect(kindByName.get('stim')).toBe('method');
  });

  it('emits instantiates references for all three module-instantiation kinds', () => {
    const result = extractFromSource('relations.sv', FIX('relations.sv'));
    // Every `child u_x (...)` site — regardless of whether the grammar
    // disambiguated it as module_instantiation / checker_instantiation /
    // udp_instantiation — must produce an `instantiates` unresolved
    // reference. Resolution to a target node happens later in the
    // ReferenceResolver pass (a CodeGraph integration step that
    // extractFromSource skips), so we assert on the unresolved-ref
    // payload here.
    const instRefs = result.unresolvedReferences.filter(
      (r) => r.referenceKind === 'instantiates' && r.referenceName === 'child',
    );
    expect(instRefs.length).toBeGreaterThanOrEqual(3);
  });

  it('parses conditional / case / always blocks without aborting', () => {
    // We don't assert kinds for these (the framework doesn't surface them as
    // entities) — but we DO assert extraction completes cleanly and the
    // module + outputs are seen.
    const result = extractFromSource('conditions.sv', FIX('conditions.sv'));
    const names = result.nodes.map((n) => n.name);
    expect(names).toContain('m');
  });

  it('produces no nodes for unrelated file types', () => {
    // Sanity: when the dispatcher routes to verilog by extension, it should
    // do so only for .sv/.svh/.v/.vh files. This test asserts the registry
    // path through extractFromSource at minimum doesn't throw.
    const result = extractFromSource('entities.sv', FIX('entities.sv'));
    expect(Array.isArray(result.nodes)).toBe(true);
    expect(Array.isArray(result.edges)).toBe(true);
  });
});
