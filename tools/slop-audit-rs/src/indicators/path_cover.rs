//! The minimum end-to-end path cover: the Eulerian-walk count. Ported from
//! l1_analyzer.path_cover.
//!
//! The question it answers: how many runs from an entry point, each following real control
//! flow to an exit, do you need so that together they traverse every branch at least once?
//! Not the number of distinct paths, which multiplies, but the minimum number of walks that
//! cover every edge. For well-behaved code this is a small, attainable number.
//!
//! The number is computed by minimum flow with a lower bound of one on every edge: each edge
//! must be walked at least once, and the walks from entry to exit are minimised. A function
//! whose control-flow graph is Eulerian answers one.
//!
//! Intraprocedural, per function and then summed. Linking calls into one interprocedural
//! graph would lower the number further and is a separate piece of work.

use crate::lang;
use crate::nodes::{children, descendants, field};
use crate::Indicator;
use std::collections::{BTreeMap, VecDeque};
use tree_sitter::Node;

/// A control-flow node: a basic-block id, or one of the two sentinels. Control that does not
/// fall through is the absence of one.
///
/// The reference spells the sentinels as strings in an integer-or-string union, which means
/// every comparison is against a value of two possible types. Here they are numbers reserved
/// at the bottom of the range, because the only thing the graph ever does with a node is use
/// it as a key.
type CfgNode = usize;

const ENTRY: CfgNode = 0;
const EXIT: CfgNode = 1;
/// The two nodes the lower-bound construction adds, reserved beside the sentinels so the
/// block counter never collides with them.
const SUPER_SRC: CfgNode = 2;
const SUPER_SINK: CfgNode = 3;
/// The first id a basic block can take.
const FIRST_BLOCK: CfgNode = 4;

const INF: i64 = 1_000_000_000;

/// Node types a control-flow walk steps over rather than into.
const SIMPLE_SKIP: &[&str] = &["comment", "newline", ":", "pass_statement"];

/// One arc of the flow graph: where it goes, what is left, and where its opposite sits.
///
/// Three named fields rather than three positions. The reference held this as a list typed
/// as a list of graph NODES while it holds a node and two numbers, so a capacity test was
/// comparing a node to a number, and fourteen sites indexed it by position.
#[derive(Debug, Clone)]
struct Edge {
    to: CfgNode,
    capacity: i64,
    back: usize,
}

type Graph = BTreeMap<CfgNode, Vec<Edge>>;

fn add(graph: &mut Graph, u: CfgNode, v: CfgNode, cap: i64) {
    let back_of_forward = graph.entry(v).or_default().len();
    graph.entry(u).or_default().push(Edge { to: v, capacity: cap, back: back_of_forward });
    let back_of_reverse = graph[&u].len() - 1;
    graph.entry(v).or_default().push(Edge { to: u, capacity: 0, back: back_of_reverse });
}

/// Edmonds-Karp: augment along a shortest residual path until none is left.
fn max_flow(graph: &mut Graph, s: CfgNode, t: CfgNode) -> i64 {
    let mut total = 0i64;
    loop {
        let mut parent: BTreeMap<CfgNode, Option<(CfgNode, usize)>> = BTreeMap::new();
        parent.insert(s, None);
        let mut queue = VecDeque::from([s]);
        while let Some(u) = queue.pop_front() {
            if u == t {
                break;
            }
            let arcs: Vec<(usize, CfgNode, i64)> = graph.get(&u).map(|edges| {
                edges.iter().enumerate().map(|(i, e)| (i, e.to, e.capacity)).collect()
            }).unwrap_or_default();
            for (i, to, capacity) in arcs {
                if capacity > 0 && !parent.contains_key(&to) {
                    parent.insert(to, Some((u, i)));
                    queue.push_back(to);
                }
            }
        }
        if !parent.contains_key(&t) {
            return total;
        }
        // The bottleneck along the path just found. Read once and then used: testing that a
        // parent is present narrows nothing about the NEXT lookup of the same key, and both
        // walks in the reference unpacked a value the checker had every reason to think
        // could be the absence they had just tested for.
        let mut bottleneck = INF;
        let mut v = t;
        while let Some(Some((u, i))) = parent.get(&v).copied() {
            bottleneck = bottleneck.min(graph[&u][i].capacity);
            v = u;
        }
        let mut v = t;
        while let Some(Some((u, i))) = parent.get(&v).copied() {
            graph.get_mut(&u).expect("the arc's owner")[i].capacity -= bottleneck;
            let back = graph[&u][i].back;
            graph.get_mut(&v).expect("the arc's opposite")[back].capacity += bottleneck;
            v = u;
        }
        total += bottleneck;
    }
}

/// Fewest source-to-sink walks covering every edge at least once, edges reusable across
/// walks. Minimum flow with a lower bound of one per edge.
///
/// Each lower bound is folded into node demand, the demands are saturated with a super
/// source and sink max flow for feasibility, and the flow is then minimised by pushing back
/// as much sink-to-source flow as the real residual allows.
fn min_path_cover(edges: &[(CfgNode, CfgNode)], source: CfgNode, sink: CfgNode) -> i64 {
    if edges.is_empty() {
        return 0;
    }
    let mut graph: Graph = BTreeMap::new();
    let mut demand: BTreeMap<CfgNode, i64> = BTreeMap::new();
    for (u, v) in edges {
        add(&mut graph, *u, *v, INF);       // upper INF; the lower bound rides on demand
        *demand.entry(*v).or_insert(0) += 1;
        *demand.entry(*u).or_insert(0) -= 1;
    }
    // The circulation edge, which carries the flow value.
    add(&mut graph, sink, source, INF);
    let (e_owner, e_idx) = (sink, graph[&sink].len() - 1);

    for (node, d) in demand.clone() {
        if d > 0 {
            add(&mut graph, SUPER_SRC, node, d);
        } else if d < 0 {
            add(&mut graph, node, SUPER_SINK, -d);
        }
    }
    max_flow(&mut graph, SUPER_SRC, SUPER_SINK);   // saturate the lower bounds

    let flow_on_e = INF - graph[&e_owner][e_idx].capacity;
    // Disable the artificial edges, the super nodes and the circulation edge, so the
    // pushback runs only over the real residual.
    for owner in [SUPER_SRC, SUPER_SINK] {
        let arcs: Vec<(CfgNode, usize)> = graph.get(&owner)
            .map(|edges| edges.iter().map(|e| (e.to, e.back)).collect())
            .unwrap_or_default();
        if let Some(edges) = graph.get_mut(&owner) {
            for edge in edges {
                edge.capacity = 0;
            }
        }
        for (to, back) in arcs {
            graph.get_mut(&to).expect("the opposite's owner")[back].capacity = 0;
        }
    }
    let e_rev = graph[&e_owner][e_idx].back;
    graph.get_mut(&e_owner).expect("the circulation edge")[e_idx].capacity = 0;
    graph.get_mut(&source).expect("the circulation edge's opposite")[e_rev].capacity = 0;

    let pushed = max_flow(&mut graph, sink, source);
    flow_on_e - pushed
}

// --- the control-flow graph, built from one function body ------------------------
//
// Two accumulators threaded explicitly: the edge list and a fresh-id source. Every builder
// takes them as parameters and binds no instance or module state, so the analyzer stays
// clean under its own L1.18, where a stateful builder would flag as mutable instance state.
// Straight-line statements are collapsed; only branches and loops create structure. `cur` is
// the current control point, and its absence means control does not fall through.

/// The fresh-id source, which is a counter and nothing else.
struct Counter(CfgNode);

impl Counter {
    fn next(&mut self) -> CfgNode {
        let id = self.0;
        self.0 += 1;
        id
    }
}

fn cfg_edge(edges: &mut Vec<(CfgNode, CfgNode)>, u: Option<CfgNode>, v: Option<CfgNode>) {
    if let (Some(u), Some(v)) = (u, v) {
        edges.push((u, v));
    }
}

fn build_block(edges: &mut Vec<(CfgNode, CfgNode)>, counter: &mut Counter, block: Option<Node>,
               mut cur: Option<CfgNode>, brk: Option<CfgNode>,
               cont: Option<CfgNode>) -> Option<CfgNode> {
    let Some(block) = block else { return cur };
    for stmt in children(block).into_iter().filter(|c| c.is_named()) {
        if SIMPLE_SKIP.contains(&stmt.kind()) {
            continue;
        }
        cur = build_stmt(edges, counter, stmt, cur, brk, cont);
    }
    cur
}

fn build_stmt(edges: &mut Vec<(CfgNode, CfgNode)>, counter: &mut Counter, stmt: Node,
              cur: Option<CfgNode>, brk: Option<CfgNode>,
              cont: Option<CfgNode>) -> Option<CfgNode> {
    match stmt.kind() {
        "return_statement" => {
            cfg_edge(edges, cur, Some(EXIT));
            None
        }
        "break_statement" => {
            cfg_edge(edges, cur, brk);
            None
        }
        "continue_statement" => {
            cfg_edge(edges, cur, cont);
            None
        }
        "if_statement" => cfg_if(edges, counter, stmt, cur, brk, cont),
        "while_statement" | "for_statement" => cfg_loop(edges, counter, stmt, cur, brk, cont),
        "match_statement" => cfg_match(edges, counter, stmt, cur, brk, cont),
        "try_statement" | "with_statement" =>
            build_block(edges, counter, field(Some(stmt), "body"), cur, brk, cont),
        // A straight-line statement, collapsed.
        _ => cur,
    }
}

fn cfg_if(edges: &mut Vec<(CfgNode, CfgNode)>, counter: &mut Counter, stmt: Node,
          cur: Option<CfgNode>, brk: Option<CfgNode>,
          cont: Option<CfgNode>) -> Option<CfgNode> {
    let merge = counter.next();
    let arm = |edges: &mut Vec<(CfgNode, CfgNode)>, counter: &mut Counter,
                   block_node: Option<Node>| -> bool {
        let start = counter.next();
        cfg_edge(edges, cur, Some(start));
        let end = build_block(edges, counter, block_node, Some(start), brk, cont);
        match end {
            Some(end) => {
                cfg_edge(edges, Some(end), Some(merge));
                true
            }
            None => false,
        }
    };
    let mut reached = arm(edges, counter, field(Some(stmt), "consequence"));
    let mut has_else = false;
    for child in children(stmt) {
        match child.kind() {
            "elif_clause" => {
                has_else = true;
                reached = arm(edges, counter, field(Some(child), "consequence")) || reached;
            }
            "else_clause" => {
                has_else = true;
                reached = arm(edges, counter, field(Some(child), "body")) || reached;
            }
            _ => {}
        }
    }
    if !has_else {
        cfg_edge(edges, cur, Some(merge));     // the branch-not-taken edge
        reached = true;
    }
    if reached { Some(merge) } else { None }
}

fn cfg_loop(edges: &mut Vec<(CfgNode, CfgNode)>, counter: &mut Counter, stmt: Node,
            cur: Option<CfgNode>, _brk: Option<CfgNode>,
            _cont: Option<CfgNode>) -> Option<CfgNode> {
    let header = counter.next();
    cfg_edge(edges, cur, Some(header));
    let after = counter.next();
    let body = field(Some(stmt), "body");
    let body_start = counter.next();
    cfg_edge(edges, Some(header), Some(body_start));   // enter the loop
    cfg_edge(edges, Some(header), Some(after));        // skip, or the condition is false
    let body_end = build_block(edges, counter, body, Some(body_start), Some(after),
                               Some(header));
    cfg_edge(edges, body_end, Some(header));           // loop back
    Some(after)
}

fn cfg_match(edges: &mut Vec<(CfgNode, CfgNode)>, counter: &mut Counter, stmt: Node,
             cur: Option<CfgNode>, brk: Option<CfgNode>,
             cont: Option<CfgNode>) -> Option<CfgNode> {
    let merge = counter.next();
    let mut arms = 0;
    let body = field(Some(stmt), "body");
    let cases: Vec<Node> = match body {
        Some(body) => children(body).into_iter().filter(|c| c.is_named()).collect(),
        None => Vec::new(),
    };
    for case in cases {
        if case.kind() != "case_clause" {
            continue;
        }
        arms += 1;
        let arm_start = counter.next();
        cfg_edge(edges, cur, Some(arm_start));
        let arm_body = field(Some(case), "consequence");
        let end = build_block(edges, counter, arm_body, Some(arm_start), brk, cont);
        cfg_edge(edges, end, Some(merge));
    }
    if arms == 0 {
        return cur;
    }
    cfg_edge(edges, cur, Some(merge));     // no case matched
    Some(merge)
}

/// The minimum entry-to-exit walks covering every branch in one function body.
pub fn function_cover(body: Node) -> i64 {
    let mut edges: Vec<(CfgNode, CfgNode)> = Vec::new();
    let mut counter = Counter(FIRST_BLOCK);
    let end = build_block(&mut edges, &mut counter, Some(body), Some(ENTRY), Some(EXIT),
                          Some(ENTRY));
    cfg_edge(&mut edges, end, Some(EXIT));     // fall through to exit
    if edges.is_empty() {
        return 1;
    }
    min_path_cover(&edges, ENTRY, EXIT).max(1)
}

/// Body node types that hold a function's statements.
const BODY_NODE_TYPES: &[&str] = &["block", "compound_statement", "body", "function_body",
                                   "body_statement", "statement_block"];

/// A number with thousands separators, the way the reference's format specifier prints it.
fn grouped(n: i64) -> String {
    let digits = n.abs().to_string();
    let mut out = String::new();
    for (i, c) in digits.chars().enumerate() {
        if i > 0 && (digits.len() - i) % 3 == 0 {
            out.push(',');
        }
        out.push(c);
    }
    if n < 0 { format!("-{out}") } else { out }
}

/// The repository-level minimum path cover: the attainable number of runs that walk every
/// branch, testing each function at its own entry, per function and summed.
pub fn analyze(repo: &std::path::Path, language: &str) -> Indicator {
    let row = |value: String, details: String| Indicator {
        code: "path_cover".into(), label: "path-cover".into(), value, band: "n/a".into(),
        details,
    };
    if language != "python" {
        return row("n/a".into(),
                   format!("path cover not implemented for {language} yet (python only)"));
    }
    let Some(cfg) = lang::cfg("python") else {
        return row("n/a".into(), "no tree-sitter config for python".into());
    };
    let (parsed, _skipped) = crate::production_files(repo, "python");
    let mut total = 0i64;
    let mut functions = 0i64;
    for (_rel, tree, _src) in &parsed {
        for n in descendants(tree.root_node()) {
            if !cfg.function_types.contains(&n.kind()) {
                continue;
            }
            if let Some(body) = children(n).into_iter()
                .find(|c| BODY_NODE_TYPES.contains(&c.kind())) {
                functions += 1;
                total += function_cover(body);
            }
        }
    }
    row(total.to_string(), format!(
        "{} end-to-end runs cover every branch across {} functions \
         (per-function edge cover, python)", grouped(total), grouped(functions)))
}
