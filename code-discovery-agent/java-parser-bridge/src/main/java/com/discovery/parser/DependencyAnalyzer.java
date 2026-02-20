package com.discovery.parser;

import com.github.javaparser.StaticJavaParser;
import com.github.javaparser.ast.CompilationUnit;
import com.github.javaparser.ast.ImportDeclaration;
import com.github.javaparser.ast.body.ClassOrInterfaceDeclaration;
import com.github.javaparser.ast.body.ConstructorDeclaration;
import com.github.javaparser.ast.body.FieldDeclaration;
import com.github.javaparser.ast.body.MethodDeclaration;
import com.github.javaparser.ast.body.Parameter;
import com.github.javaparser.ast.expr.AnnotationExpr;

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

public class DependencyAnalyzer {

    private static final Set<String> SPRING_ANNOTATIONS = Set.of(
            "Component", "Service", "Repository", "Controller", "RestController",
            "Configuration", "Bean", "Autowired", "Value", "Qualifier",
            "EnableBatchProcessing", "StepScope", "JobScope",
            "Transactional", "Scheduled", "Async", "Primary",
            "ConditionalOnProperty", "Profile", "Import", "ComponentScan"
    );

    private static final Set<String> PRIMITIVE_TYPES = Set.of(
            "String", "int", "long", "double", "float", "boolean",
            "Integer", "Long", "Double", "Float", "Boolean",
            "List", "Map", "Set", "Optional", "byte", "short", "char",
            "Byte", "Short", "Character", "Object", "Class", "void"
    );

    public List<Map<String, Object>> analyzeDirectory(Path directory) throws IOException {
        List<Map<String, Object>> allDeps = new ArrayList<>();

        try (Stream<Path> paths = Files.walk(directory)) {
            List<Path> javaFiles = paths
                    .filter(p -> p.toString().endsWith(".java"))
                    .filter(p -> !p.toString().contains("/target/"))
                    .filter(p -> !p.toString().contains("/build/"))
                    .toList();

            for (Path file : javaFiles) {
                try {
                    CompilationUnit cu = StaticJavaParser.parse(file);
                    List<Map<String, Object>> fileDeps = analyzeFile(cu, file.toString());
                    allDeps.addAll(fileDeps);
                } catch (Exception e) {
                    System.err.println("Error analyzing " + file + ": " + e.getMessage());
                }
            }
        }

        return allDeps;
    }

    private List<Map<String, Object>> analyzeFile(CompilationUnit cu, String filePath) {
        List<Map<String, Object>> deps = new ArrayList<>();

        String packageName = cu.getPackageDeclaration()
                .map(pd -> pd.getNameAsString())
                .orElse("");

        List<String> imports = cu.getImports().stream()
                .map(ImportDeclaration::getNameAsString)
                .toList();

        cu.findAll(ClassOrInterfaceDeclaration.class).forEach(classDecl -> {
            Map<String, Object> dep = new HashMap<>();
            String className = classDecl.getNameAsString();
            String fqn = packageName.isEmpty() ? className : packageName + "." + className;

            dep.put("class_name", fqn);
            dep.put("short_name", className);
            dep.put("file_path", filePath);
            dep.put("imports", imports);

            List<String> springAnnotations = extractSpringAnnotations(classDecl);
            dep.put("spring_annotations", springAnnotations);

            List<String> fieldDeps = extractFieldDependencies(classDecl);
            dep.put("field_dependencies", fieldDeps);

            List<String> constructorDeps = extractConstructorDependencies(classDecl);
            dep.put("constructor_dependencies", constructorDeps);

            List<String> setterDeps = extractSetterDependencies(classDecl);
            dep.put("setter_dependencies", setterDeps);

            Set<String> allDepTypes = new HashSet<>();
            allDepTypes.addAll(fieldDeps);
            allDepTypes.addAll(constructorDeps);
            allDepTypes.addAll(setterDeps);
            dep.put("depends_on", new ArrayList<>(allDepTypes));

            List<String> extendsList = classDecl.getExtendedTypes().stream()
                    .map(t -> t.getNameAsString())
                    .toList();
            dep.put("extends", extendsList);

            List<String> implementsList = classDecl.getImplementedTypes().stream()
                    .map(t -> t.getNameAsString())
                    .toList();
            dep.put("implements", implementsList);

            boolean isShared = isSharedComponent(className, springAnnotations);
            dep.put("is_shared", isShared);

            deps.add(dep);
        });

        return deps;
    }

    private List<String> extractSpringAnnotations(ClassOrInterfaceDeclaration classDecl) {
        List<String> annotations = new ArrayList<>();

        classDecl.getAnnotations().forEach(ann -> {
            String name = ann.getNameAsString();
            if (SPRING_ANNOTATIONS.contains(name)) {
                annotations.add(name);
            }
        });

        classDecl.getMethods().forEach(method -> {
            method.getAnnotations().forEach(ann -> {
                String name = ann.getNameAsString();
                if (SPRING_ANNOTATIONS.contains(name) && !annotations.contains(name)) {
                    annotations.add(name);
                }
            });
        });

        classDecl.getFields().forEach(field -> {
            field.getAnnotations().forEach(ann -> {
                String name = ann.getNameAsString();
                if (SPRING_ANNOTATIONS.contains(name) && !annotations.contains(name)) {
                    annotations.add(name);
                }
            });
        });

        return annotations;
    }

    private List<String> extractFieldDependencies(ClassOrInterfaceDeclaration classDecl) {
        List<String> deps = new ArrayList<>();

        classDecl.getFields().forEach(field -> {
            boolean isInjected = field.getAnnotations().stream()
                    .anyMatch(a -> {
                        String name = a.getNameAsString();
                        return name.equals("Autowired") || name.equals("Inject")
                                || name.equals("Resource");
                    });

            if (isInjected) {
                String typeName = field.getElementType().asString();
                if (!PRIMITIVE_TYPES.contains(typeName)) {
                    deps.add(typeName);
                }
            }
        });

        return deps;
    }

    private List<String> extractConstructorDependencies(ClassOrInterfaceDeclaration classDecl) {
        List<String> deps = new ArrayList<>();

        classDecl.getConstructors().forEach(constructor -> {
            constructor.getParameters().forEach(param -> {
                String typeName = param.getTypeAsString();
                String baseName = typeName.contains("<")
                        ? typeName.substring(0, typeName.indexOf('<'))
                        : typeName;
                if (!PRIMITIVE_TYPES.contains(baseName)) {
                    deps.add(baseName);
                }
            });
        });

        return deps;
    }

    private List<String> extractSetterDependencies(ClassOrInterfaceDeclaration classDecl) {
        List<String> deps = new ArrayList<>();

        classDecl.getMethods().stream()
                .filter(m -> m.getAnnotations().stream()
                        .anyMatch(a -> {
                            String name = a.getNameAsString();
                            return name.equals("Autowired") || name.equals("Inject")
                                    || name.equals("Resource");
                        }))
                .forEach(method -> {
                    method.getParameters().forEach(param -> {
                        String typeName = param.getTypeAsString();
                        String baseName = typeName.contains("<")
                                ? typeName.substring(0, typeName.indexOf('<'))
                                : typeName;
                        if (!PRIMITIVE_TYPES.contains(baseName)) {
                            deps.add(baseName);
                        }
                    });
                });

        return deps;
    }

    private boolean isSharedComponent(String className, List<String> annotations) {
        Set<String> sharedIndicators = Set.of(
                "Common", "Shared", "Base", "Abstract", "Default", "Generic", "Util"
        );

        if (sharedIndicators.stream().anyMatch(className::contains)) {
            return true;
        }

        if (annotations.contains("Configuration") || annotations.contains("Component")) {
            if (!annotations.contains("EnableBatchProcessing")) {
                return true;
            }
        }

        return false;
    }
}
