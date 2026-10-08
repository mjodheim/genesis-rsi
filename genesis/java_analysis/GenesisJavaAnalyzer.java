import java.nio.file.*;
import java.util.*;
import javax.lang.model.element.*;
import javax.tools.*;
import com.sun.source.tree.*;
import com.sun.source.util.*;
import com.sun.source.util.JavacTask;

/**
 * G11: read-only Java structural and partial semantic analysis.
 * No patches, tests, benchmark identifiers or solution material are read.
 * Compiler errors are reported; unresolved types/symbols remain explicitly unknown.
 */
public final class GenesisJavaAnalyzer {
  static String q(String s) {
    if (s == null) return "null";
    StringBuilder b = new StringBuilder("\"");
    for (char c : s.toCharArray()) {
      if (c == '"' || c == '\\') b.append('\\');
      if (c == '\n') b.append("\\n");
      else if (c == '\r') b.append("\\r");
      else if (c == '\t') b.append("\\t");
      else if (c < 32) b.append(String.format("\\u%04x", (int)c));
      else b.append(c);
    }
    return b.append('"').toString();
  }
  static String record(Object... kv) {
    StringBuilder b = new StringBuilder("{");
    for (int i = 0; i < kv.length; i += 2) {
      if (i > 0) b.append(',');
      b.append(q((String)kv[i])).append(':');
      Object v = kv[i + 1];
      if (v == null) b.append("null");
      else if (v instanceof Number || v instanceof Boolean) b.append(v);
      else b.append(q(v.toString()));
    }
    return b.append('}').toString();
  }
  static String arr(Collection<String> items) { return "[" + String.join(",", items) + "]"; }
  static long start(SourcePositions positions, CompilationUnitTree unit, Tree tree) {
    return tree == null ? -1 : positions.getStartPosition(unit, tree);
  }
  static long end(SourcePositions positions, CompilationUnitTree unit, Tree tree) {
    return tree == null ? -1 : positions.getEndPosition(unit, tree);
  }
  static String elementId(Element e, Trees trees, CompilationUnitTree unit, SourcePositions positions) {
    if (e == null) return null;
    // Declaration position disambiguates shadowed locals and overloads.
    Tree decl = trees.getTree(e);
    long position = decl == null ? -1 : start(positions, unit, decl);
    return e.getKind() + ":" + String.valueOf(e.getEnclosingElement()) + ":" + e + ":" + position;
  }

  static final class Extract extends TreePathScanner<Void, Void> {
    final Trees trees;
    final CompilationUnitTree unit;
    final SourcePositions pos;
    final List<String> nodes = new ArrayList<>();
    final List<String> branches = new ArrayList<>();
    final List<String> accesses = new ArrayList<>();
    final List<String> calls = new ArrayList<>();
    Extract(Trees t, CompilationUnitTree u) {
      trees=t; unit=u; pos=t.getSourcePositions();
    }
    String type(TreePath path) {
      try {
        javax.lang.model.type.TypeMirror t = trees.getTypeMirror(path);
        if (t == null || t.getKind() == javax.lang.model.type.TypeKind.ERROR) return null;
        return t.toString();
      } catch (RuntimeException ex) { return null; }
    }
    Element element(TreePath path) {
      try { return trees.getElement(path); }
      catch (RuntimeException ex) { return null; }
    }
    String id(Element e) { return elementId(e, trees, unit, pos); }
    void access(Tree tree, String mode) {
      TreePath path = new TreePath(getCurrentPath(), tree);
      Element e = element(path);
      if (!(e instanceof VariableElement)) return;
      long s = start(pos, unit, tree), end = end(pos, unit, tree);
      if (s < 0 || end < s) return;
      accesses.add(record("mode",mode,"name",e.getSimpleName(),"symbol_id",id(e),
          "type",e.asType(),"start",s,"end",end));
    }
    @Override public Void scan(Tree tree, Void ignored) {
      if (tree != null) {
        long s = start(pos, unit, tree), e = end(pos, unit, tree);
        if (s >= 0 && e >= s) {
          String name = "";
          if (tree instanceof MethodTree) name = ((MethodTree)tree).getName().toString();
          else if (tree instanceof ClassTree) name = ((ClassTree)tree).getSimpleName().toString();
          else if (tree instanceof VariableTree) name = ((VariableTree)tree).getName().toString();
          TreePath path = getCurrentPath() == null ? null : new TreePath(getCurrentPath(), tree);
          Element sym = path == null ? null : element(path);
          nodes.add(record("kind",tree.getKind().name(),"start",s,"end",e,"name",name,
              "type",path == null ? null : type(path),"symbol_id",id(sym)));
        }
      }
      return super.scan(tree, ignored);
    }
    @Override public Void visitIf(IfTree t, Void unused) {
      branches.add(record("kind","IF","start",start(pos,unit,t),"end",end(pos,unit,t),
          "condition_start",start(pos,unit,t.getCondition()),"condition_end",end(pos,unit,t.getCondition()),
          "then_start",start(pos,unit,t.getThenStatement()),"then_end",end(pos,unit,t.getThenStatement()),
          "else_start",start(pos,unit,t.getElseStatement()),"else_end",end(pos,unit,t.getElseStatement())));
      return super.visitIf(t, unused);
    }
    @Override public Void visitWhileLoop(WhileLoopTree t, Void unused) {
      branches.add(record("kind","WHILE_LOOP","start",start(pos,unit,t),"end",end(pos,unit,t),
          "condition_start",start(pos,unit,t.getCondition()),"condition_end",end(pos,unit,t.getCondition()),
          "then_start",start(pos,unit,t.getStatement()),"then_end",end(pos,unit,t.getStatement())));
      return super.visitWhileLoop(t, unused);
    }
    @Override public Void visitConditionalExpression(ConditionalExpressionTree t, Void unused) {
      branches.add(record("kind","CONDITIONAL_EXPRESSION","start",start(pos,unit,t),"end",end(pos,unit,t),
          "condition_start",start(pos,unit,t.getCondition()),"condition_end",end(pos,unit,t.getCondition()),
          "then_start",start(pos,unit,t.getTrueExpression()),"then_end",end(pos,unit,t.getTrueExpression()),
          "else_start",start(pos,unit,t.getFalseExpression()),"else_end",end(pos,unit,t.getFalseExpression())));
      return super.visitConditionalExpression(t, unused);
    }
    @Override public Void visitVariable(VariableTree t, Void unused) {
      Element e = element(getCurrentPath());
      if (e instanceof VariableElement) {
        accesses.add(record("mode","declare","name",e.getSimpleName(),"symbol_id",id(e),
            "type",e.asType(),"start",start(pos,unit,t),"end",end(pos,unit,t)));
      }
      return super.visitVariable(t, unused);
    }
    @Override public Void visitIdentifier(IdentifierTree t, Void unused) {
      Element e = element(getCurrentPath());
      if (e instanceof VariableElement) {
        accesses.add(record("mode","read","name",e.getSimpleName(),"symbol_id",id(e),
            "type",e.asType(),"start",start(pos,unit,t),"end",end(pos,unit,t)));
      }
      return super.visitIdentifier(t, unused);
    }
    @Override public Void visitAssignment(AssignmentTree t, Void unused) {
      access(t.getVariable(), "write");
      return super.visitAssignment(t, unused);
    }
    @Override public Void visitCompoundAssignment(CompoundAssignmentTree t, Void unused) {
      access(t.getVariable(), "read_write");
      return super.visitCompoundAssignment(t, unused);
    }
    @Override public Void visitMethodInvocation(MethodInvocationTree t, Void unused) {
      Element e = element(getCurrentPath());
      calls.add(record("start",start(pos,unit,t),"end",end(pos,unit,t),
          "method",e == null ? null : e.toString(),
          "target_id",e instanceof ExecutableElement ? id(e) : null,
          "resolved",e instanceof ExecutableElement));
      return super.visitMethodInvocation(t, unused);
    }
  }

  public static void main(String[] args) throws Exception {
    if (args.length != 1 && args.length != 2)
      throw new IllegalArgumentException("Usage: GenesisJavaAnalyzer SOURCE.java [CLASSPATH]");
    Path source = Paths.get(args[0]).toAbsolutePath().normalize();
    if (!Files.isRegularFile(source) || !source.getFileName().toString().endsWith(".java"))
      throw new IllegalArgumentException("Source must be a readable Java file");
    JavaCompiler compiler = ToolProvider.getSystemJavaCompiler();
    if (compiler == null) throw new IllegalStateException("JDK compiler required");
    DiagnosticCollector<JavaFileObject> diagnostics = new DiagnosticCollector<>();
    try (StandardJavaFileManager fm = compiler.getStandardFileManager(diagnostics, null, null)) {
      List<String> opts = new ArrayList<>(Arrays.asList("-proc:none","-implicit:none","-Xlint:none"));
      if (args.length == 2 && !args[1].isEmpty()) {
        opts.add("-classpath"); opts.add(args[1]);
      }
      JavacTask task = (JavacTask) compiler.getTask(null, fm, diagnostics, opts, null,
          fm.getJavaFileObjects(source.toFile()));
      List<CompilationUnitTree> units = new ArrayList<>();
      for (CompilationUnitTree unit : task.parse()) units.add(unit);
      // Partial symbol/type resolution is retained even if external classes are missing.
      try { task.analyze(); } catch (RuntimeException ex) {
        // Fail with an explicit diagnostic count; never invent resolved symbols.
        diagnostics.report(new Diagnostic<JavaFileObject>() {
          public Kind getKind(){return Kind.ERROR;}
          public JavaFileObject getSource(){return null;}
          public long getPosition(){return -1;}
          public long getStartPosition(){return -1;}
          public long getEndPosition(){return -1;}
          public long getLineNumber(){return -1;}
          public long getColumnNumber(){return -1;}
          public String getCode(){return "genesis.analyze.failure";}
          public String getMessage(Locale locale){return ex.getClass().getName();}
        });
      }
      Trees trees = Trees.instance(task);
      List<String> nodes = new ArrayList<>(), branches = new ArrayList<>(),
          accesses = new ArrayList<>(), calls = new ArrayList<>();
      for (CompilationUnitTree u : units) {
        Extract e = new Extract(trees,u);
        e.scan(u,null);
        nodes.addAll(e.nodes); branches.addAll(e.branches);
        accesses.addAll(e.accesses); calls.addAll(e.calls);
      }
      long errors = diagnostics.getDiagnostics().stream()
          .filter(d -> d.getKind() == Diagnostic.Kind.ERROR).count();
      System.out.println("{\"schema\":\"genesis-java-understanding-v2\",\"nodes\":" + arr(nodes)
          + ",\"branches\":" + arr(branches) + ",\"accesses\":" + arr(accesses)
          + ",\"calls\":" + arr(calls) + ",\"error_count\":" + errors + "}");
    }
  }
}
