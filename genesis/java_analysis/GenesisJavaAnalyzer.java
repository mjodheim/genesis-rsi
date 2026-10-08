import java.io.*;
import java.nio.file.*;
import java.util.*;
import javax.tools.*;
import com.sun.source.tree.*;
import com.sun.source.util.*;

/** Read-only compiler AST extraction. No benchmark answers or patch material. */
public final class GenesisJavaAnalyzer {
  private static String quote(String s) {
    StringBuilder b = new StringBuilder("\"");
    for (char c : s.toCharArray()) {
      if (c == '"' || c == '\\') b.append('\\');
      if (c == '\n') b.append("\\n"); else if (c == '\r') b.append("\\r");
      else if (c == '\t') b.append("\\t"); else if (c < 32) b.append(String.format("\\u%04x", (int)c)); else b.append(c);
    }
    return b.append('"').toString();
  }
  public static void main(String[] args) throws Exception {
    if (args.length != 1) throw new IllegalArgumentException("Expected exactly one Java source path");
    Path source = Paths.get(args[0]).toAbsolutePath().normalize();
    JavaCompiler compiler = ToolProvider.getSystemJavaCompiler();
    if (compiler == null) throw new IllegalStateException("JDK compiler required");
    try (StandardJavaFileManager fm = compiler.getStandardFileManager(null, null, null)) {
      Iterable<? extends JavaFileObject> files = fm.getJavaFileObjects(source.toFile());
      JavacTask task = (JavacTask) compiler.getTask(null, fm, null, Arrays.asList("-proc:none"), null, files);
      StringBuilder out = new StringBuilder("{\"schema\":\"genesis-java-ast-v1\",\"nodes\":[");
      boolean first = true;
      for (CompilationUnitTree unit : task.parse()) {
        Trees trees = Trees.instance(task);
        SourcePositions positions = trees.getSourcePositions();
        List<String> nodes = new ArrayList<>();
        new TreePathScanner<Void,Void>() {
          @Override public Void scan(Tree tree, Void unused) {
            if (tree != null) {
              long start = positions.getStartPosition(unit, tree);
              long end = positions.getEndPosition(unit, tree);
              if (start >= 0 && end >= start) {
                String name = "";
                if (tree instanceof MethodTree) name = ((MethodTree)tree).getName().toString();
                else if (tree instanceof ClassTree) name = ((ClassTree)tree).getSimpleName().toString();
                else if (tree instanceof VariableTree) name = ((VariableTree)tree).getName().toString();
                nodes.add("{\"kind\":" + quote(tree.getKind().name()) + ",\"start\":" + start + ",\"end\":" + end + ",\"name\":" + quote(name) + "}");
              }
            }
            return super.scan(tree, unused);
          }
        }.scan(unit, null);
        for (String node : nodes) { if (!first) out.append(','); first=false; out.append(node); }
      }
      System.out.println(out.append("]}").toString());
    }
  }
}
