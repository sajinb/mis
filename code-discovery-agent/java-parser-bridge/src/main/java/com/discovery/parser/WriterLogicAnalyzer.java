package com.discovery.parser;

import com.github.javaparser.StaticJavaParser;
import com.github.javaparser.ast.CompilationUnit;
import com.github.javaparser.ast.body.ClassOrInterfaceDeclaration;
import com.github.javaparser.ast.body.MethodDeclaration;
import com.github.javaparser.ast.expr.LambdaExpr;
import com.github.javaparser.ast.expr.MethodCallExpr;
import com.github.javaparser.ast.stmt.ForEachStmt;
import com.github.javaparser.ast.stmt.ForStmt;
import com.github.javaparser.ast.stmt.IfStmt;
import com.github.javaparser.ast.stmt.SwitchStmt;
import com.github.javaparser.ast.type.ClassOrInterfaceType;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.stream.Stream;

public class WriterLogicAnalyzer {

    private static final Set<String> PURE_WRITE_METHODS = Set.of(
            "write", "update", "insert", "execute", "save", "saveAll",
            "flush", "commit", "batchUpdate", "persist", "merge"
    );

    private static final Set<String> SERVICE_CALL_INDICATORS = Set.of(
            "Service", "Client", "Repository", "restTemplate", "webClient",
            "httpClient", "RestTemplate", "WebClient"
    );

    private static final Set<String> TRANSFORM_METHODS = Set.of(
            "parseInt", "parseLong", "parseDouble", "valueOf", "format",
            "toLowerCase", "toUpperCase", "trim", "replace", "substring",
            "split", "join", "matches"
    );

    public List<Map<String, Object>> analyzeDirectory(Path directory) throws IOException {
        List<Map<String, Object>> results = new ArrayList<>();

        try (Stream<Path> paths = Files.walk(directory)) {
            List<Path> javaFiles = paths
                    .filter(p -> p.toString().endsWith(".java"))
                    .filter(p -> !p.toString().contains("/target/"))
                    .filter(p -> !p.toString().contains("/build/"))
                    .toList();

            for (Path file : javaFiles) {
                try {
                    CompilationUnit cu = StaticJavaParser.parse(file);
                    List<Map<String, Object>> fileResults = analyzeFile(cu, file.toString());
                    results.addAll(fileResults);
                } catch (Exception e) {
                    System.err.println("Error analyzing " + file + ": " + e.getMessage());
                }
            }
        }

        return results;
    }

    private List<Map<String, Object>> analyzeFile(CompilationUnit cu, String filePath) {
        List<Map<String, Object>> results = new ArrayList<>();

        cu.findAll(ClassOrInterfaceDeclaration.class).forEach(classDecl -> {
            if (isWriterClass(classDecl)) {
                analyzeWriterClass(classDecl, filePath, results);
            }
        });

        cu.findAll(MethodDeclaration.class).forEach(method -> {
            if (method.getAnnotationByName("Bean").isPresent()) {
                analyzeWriterBeanMethod(method, filePath, results);
            }
        });

        return results;
    }

    private boolean isWriterClass(ClassOrInterfaceDeclaration classDecl) {
        if (classDecl.getImplementedTypes().stream()
                .anyMatch(t -> t.getNameAsString().contains("Writer"))) {
            return true;
        }

        if (classDecl.getExtendedTypes().stream()
                .anyMatch(t -> t.getNameAsString().contains("Writer"))) {
            return true;
        }

        return false;
    }

    private void analyzeWriterClass(ClassOrInterfaceDeclaration classDecl,
                                     String filePath,
                                     List<Map<String, Object>> results) {
        String className = classDecl.getNameAsString();

        classDecl.getMethods().stream()
                .filter(m -> m.getNameAsString().equals("write")
                        || m.getNameAsString().equals("doWrite")
                        || m.getNameAsString().equals("writeItems")
                        || m.getNameAsString().equals("processAndWrite"))
                .forEach(method -> {
                    Map<String, Object> analysis = analyzeMethodBody(method);
                    if ((boolean) analysis.get("has_embedded_logic")) {
                        Map<String, Object> result = new HashMap<>();
                        result.put("class_name", className);
                        result.put("method_name", method.getNameAsString());
                        result.put("file_path", filePath);
                        result.put("detection_type", "class_implementation");
                        result.put("analysis", analysis);
                        result.put("method_source", method.toString());
                        result.put("line_start", method.getBegin()
                                .map(p -> p.line).orElse(0));
                        result.put("line_end", method.getEnd()
                                .map(p -> p.line).orElse(0));
                        results.add(result);
                    }
                });
    }

    private void analyzeWriterBeanMethod(MethodDeclaration method,
                                          String filePath,
                                          List<Map<String, Object>> results) {
        String returnType = method.getTypeAsString();
        if (!returnType.contains("ItemWriter") && !returnType.contains("Writer")) {
            return;
        }

        List<LambdaExpr> lambdas = method.findAll(LambdaExpr.class);
        if (lambdas.isEmpty()) return;

        for (LambdaExpr lambda : lambdas) {
            Map<String, Object> analysis = analyzeLambdaBody(lambda);
            if ((boolean) analysis.get("has_embedded_logic")) {
                Map<String, Object> result = new HashMap<>();
                result.put("class_name", method.getNameAsString());
                result.put("method_name", method.getNameAsString() + "::lambda");
                result.put("file_path", filePath);
                result.put("detection_type", "lambda_writer");
                result.put("analysis", analysis);
                result.put("method_source", lambda.toString());
                result.put("line_start", lambda.getBegin()
                        .map(p -> p.line).orElse(0));
                result.put("line_end", lambda.getEnd()
                        .map(p -> p.line).orElse(0));
                results.add(result);
            }
        }
    }

    private Map<String, Object> analyzeMethodBody(MethodDeclaration method) {
        Map<String, Object> analysis = new HashMap<>();
        List<Map<String, String>> transformations = new ArrayList<>();

        int ifCount = method.findAll(IfStmt.class).size();
        int switchCount = method.findAll(SwitchStmt.class).size();
        int forCount = method.findAll(ForStmt.class).size();
        int forEachCount = method.findAll(ForEachStmt.class).size();

        if (ifCount > 0 || switchCount > 0) {
            Map<String, String> t = new HashMap<>();
            t.put("description", "Conditional logic (if/switch)");
            t.put("count", String.valueOf(ifCount + switchCount));
            transformations.add(t);
        }

        Set<String> serviceCalls = findServiceCalls(method);
        if (!serviceCalls.isEmpty()) {
            Map<String, String> t = new HashMap<>();
            t.put("description", "External service calls");
            t.put("details", String.join(", ", serviceCalls));
            transformations.add(t);
        }

        Set<String> transforms = findTransformCalls(method);
        if (transforms.size() >= 2) {
            Map<String, String> t = new HashMap<>();
            t.put("description", "Data transformation logic");
            t.put("details", String.join(", ", transforms));
            transformations.add(t);
        }

        int setterCount = countSetterCalls(method);
        if (setterCount >= 3) {
            Map<String, String> t = new HashMap<>();
            t.put("description", "Data enrichment (multiple setters)");
            t.put("count", String.valueOf(setterCount));
            transformations.add(t);
        }

        boolean hasStreamOps = method.findAll(MethodCallExpr.class).stream()
                .anyMatch(c -> {
                    String name = c.getNameAsString();
                    return name.equals("stream") || name.equals("filter")
                            || name.equals("map") || name.equals("collect");
                });
        if (hasStreamOps) {
            Map<String, String> t = new HashMap<>();
            t.put("description", "Stream API operations");
            transformations.add(t);
        }

        int totalStatements = method.getBody()
                .map(b -> b.getStatements().size()).orElse(0);
        int pureWriteStatements = countPureWriteStatements(method);
        double logicRatio = totalStatements > 0
                ? (double) (totalStatements - pureWriteStatements) / totalStatements
                : 0;

        boolean hasEmbeddedLogic = !transformations.isEmpty() || logicRatio > 0.5;

        analysis.put("has_embedded_logic", hasEmbeddedLogic);
        analysis.put("transformations", transformations);
        analysis.put("logic_ratio", logicRatio);
        analysis.put("total_statements", totalStatements);
        analysis.put("pure_write_statements", pureWriteStatements);
        analysis.put("if_count", ifCount);
        analysis.put("loop_count", forCount + forEachCount);

        return analysis;
    }

    private Map<String, Object> analyzeLambdaBody(LambdaExpr lambda) {
        Map<String, Object> analysis = new HashMap<>();
        List<Map<String, String>> transformations = new ArrayList<>();

        int ifCount = lambda.findAll(IfStmt.class).size();
        int switchCount = lambda.findAll(SwitchStmt.class).size();

        if (ifCount > 0 || switchCount > 0) {
            Map<String, String> t = new HashMap<>();
            t.put("description", "Conditional logic (if/switch) in lambda writer");
            t.put("count", String.valueOf(ifCount + switchCount));
            transformations.add(t);
        }

        Set<String> serviceCalls = new HashSet<>();
        lambda.findAll(MethodCallExpr.class).forEach(call -> {
            String scope = call.getScope().map(Object::toString).orElse("");
            if (SERVICE_CALL_INDICATORS.stream().anyMatch(scope::contains)) {
                serviceCalls.add(scope + "." + call.getNameAsString());
            }
        });
        if (!serviceCalls.isEmpty()) {
            Map<String, String> t = new HashMap<>();
            t.put("description", "External service calls in lambda writer");
            t.put("details", String.join(", ", serviceCalls));
            transformations.add(t);
        }

        int setterCount = (int) lambda.findAll(MethodCallExpr.class).stream()
                .filter(c -> c.getNameAsString().startsWith("set"))
                .count();
        if (setterCount >= 3) {
            Map<String, String> t = new HashMap<>();
            t.put("description", "Data enrichment in lambda writer (multiple setters)");
            t.put("count", String.valueOf(setterCount));
            transformations.add(t);
        }

        Set<String> transforms = new HashSet<>();
        lambda.findAll(MethodCallExpr.class).forEach(call -> {
            if (TRANSFORM_METHODS.contains(call.getNameAsString())) {
                transforms.add(call.getNameAsString());
            }
        });
        if (transforms.size() >= 2) {
            Map<String, String> t = new HashMap<>();
            t.put("description", "Data transformation in lambda writer");
            t.put("details", String.join(", ", transforms));
            transformations.add(t);
        }

        boolean hasArithmetic = lambda.toString().contains(" * ")
                || lambda.toString().contains(" + ")
                || lambda.toString().contains(" - ")
                || lambda.toString().contains(" / ");
        if (hasArithmetic) {
            Map<String, String> t = new HashMap<>();
            t.put("description", "Arithmetic calculations in lambda writer");
            transformations.add(t);
        }

        boolean hasEmbeddedLogic = !transformations.isEmpty();

        analysis.put("has_embedded_logic", hasEmbeddedLogic);
        analysis.put("transformations", transformations);
        analysis.put("if_count", ifCount);
        analysis.put("setter_count", setterCount);

        return analysis;
    }

    private Set<String> findServiceCalls(MethodDeclaration method) {
        Set<String> calls = new HashSet<>();
        method.findAll(MethodCallExpr.class).forEach(call -> {
            String scope = call.getScope().map(Object::toString).orElse("");
            if (SERVICE_CALL_INDICATORS.stream().anyMatch(scope::contains)) {
                calls.add(scope + "." + call.getNameAsString());
            }
        });
        return calls;
    }

    private Set<String> findTransformCalls(MethodDeclaration method) {
        Set<String> transforms = new HashSet<>();
        method.findAll(MethodCallExpr.class).forEach(call -> {
            if (TRANSFORM_METHODS.contains(call.getNameAsString())) {
                transforms.add(call.getNameAsString());
            }
        });
        return transforms;
    }

    private int countSetterCalls(MethodDeclaration method) {
        return (int) method.findAll(MethodCallExpr.class).stream()
                .filter(c -> c.getNameAsString().startsWith("set"))
                .count();
    }

    private int countPureWriteStatements(MethodDeclaration method) {
        return (int) method.findAll(MethodCallExpr.class).stream()
                .filter(c -> PURE_WRITE_METHODS.contains(c.getNameAsString()))
                .count();
    }
}
