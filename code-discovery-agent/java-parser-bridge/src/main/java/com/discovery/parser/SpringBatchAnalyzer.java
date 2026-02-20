package com.discovery.parser;

import com.github.javaparser.StaticJavaParser;
import com.github.javaparser.ast.CompilationUnit;
import com.github.javaparser.ast.body.ClassOrInterfaceDeclaration;
import com.github.javaparser.ast.body.MethodDeclaration;
import com.github.javaparser.ast.expr.AnnotationExpr;
import com.github.javaparser.ast.expr.LambdaExpr;
import com.github.javaparser.ast.expr.MethodCallExpr;
import com.github.javaparser.ast.expr.ObjectCreationExpr;
import com.github.javaparser.ast.expr.StringLiteralExpr;
import com.github.javaparser.ast.type.Type;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.Set;
import java.util.stream.Stream;

public class SpringBatchAnalyzer {

    private static final Set<String> READER_TYPES = Set.of(
            "FlatFileItemReader", "JdbcCursorItemReader", "JdbcPagingItemReader",
            "JpaPagingItemReader", "StaxEventItemReader", "JsonItemReader",
            "KafkaItemReader", "MongoItemReader", "RepositoryItemReader",
            "AmqpItemReader", "MultiResourceItemReader", "SynchronizedItemStreamReader"
    );

    private static final Set<String> WRITER_TYPES = Set.of(
            "FlatFileItemWriter", "JdbcBatchItemWriter", "JpaItemWriter",
            "StaxEventItemWriter", "JsonFileItemWriter", "KafkaItemWriter",
            "MongoItemWriter", "RepositoryItemWriter", "CompositeItemWriter",
            "ClassifierCompositeItemWriter", "AmqpItemWriter",
            "MultiResourceItemWriter", "SynchronizedItemStreamWriter"
    );

    private static final Set<String> PROCESSOR_TYPES = Set.of(
            "ItemProcessor", "CompositeItemProcessor", "ClassifierCompositeItemProcessor",
            "ValidatingItemProcessor", "BeanValidatingItemProcessor",
            "FunctionItemProcessor", "ScriptItemProcessor"
    );

    private static final Map<String, String> READER_SOURCE_MAP = Map.ofEntries(
            Map.entry("FlatFileItemReader", "FILE"),
            Map.entry("JdbcCursorItemReader", "DATABASE"),
            Map.entry("JdbcPagingItemReader", "DATABASE"),
            Map.entry("JpaPagingItemReader", "DATABASE"),
            Map.entry("StaxEventItemReader", "XML_FILE"),
            Map.entry("JsonItemReader", "JSON_FILE"),
            Map.entry("KafkaItemReader", "KAFKA"),
            Map.entry("MongoItemReader", "MONGODB"),
            Map.entry("AmqpItemReader", "AMQP")
    );

    private static final Map<String, String> WRITER_TARGET_MAP = Map.ofEntries(
            Map.entry("FlatFileItemWriter", "FILE"),
            Map.entry("JdbcBatchItemWriter", "DATABASE"),
            Map.entry("JpaItemWriter", "DATABASE"),
            Map.entry("StaxEventItemWriter", "XML_FILE"),
            Map.entry("JsonFileItemWriter", "JSON_FILE"),
            Map.entry("KafkaItemWriter", "KAFKA"),
            Map.entry("MongoItemWriter", "MONGODB"),
            Map.entry("AmqpItemWriter", "AMQP")
    );

    public List<Map<String, Object>> analyzeDirectory(Path directory) throws IOException {
        List<Map<String, Object>> allJobs = new ArrayList<>();

        try (Stream<Path> paths = Files.walk(directory)) {
            List<Path> javaFiles = paths
                    .filter(p -> p.toString().endsWith(".java"))
                    .filter(p -> !p.toString().contains("/target/"))
                    .filter(p -> !p.toString().contains("/build/"))
                    .toList();

            for (Path file : javaFiles) {
                try {
                    String source = Files.readString(file);
                    if (!isBatchConfig(source)) continue;

                    CompilationUnit cu = StaticJavaParser.parse(file);
                    List<Map<String, Object>> jobs = analyzeCompilationUnit(cu, file.toString());
                    allJobs.addAll(jobs);
                } catch (Exception e) {
                    System.err.println("Error parsing " + file + ": " + e.getMessage());
                }
            }
        }

        return allJobs;
    }

    private boolean isBatchConfig(String source) {
        return source.contains("@EnableBatchProcessing")
                || source.contains("JobBuilderFactory")
                || source.contains("StepBuilderFactory")
                || source.contains("ItemReader")
                || source.contains("ItemProcessor")
                || source.contains("ItemWriter")
                || source.contains("org.springframework.batch");
    }

    private List<Map<String, Object>> analyzeCompilationUnit(CompilationUnit cu, String filePath) {
        List<Map<String, Object>> jobs = new ArrayList<>();

        cu.findAll(ClassOrInterfaceDeclaration.class).stream()
                .filter(this::hasBatchAnnotations)
                .forEach(classDecl -> {
                    List<MethodDeclaration> beanMethods = classDecl.getMethods().stream()
                            .filter(this::isBeanMethod)
                            .toList();

                    List<MethodDeclaration> jobMethods = beanMethods.stream()
                            .filter(m -> isJobBean(m))
                            .toList();
                    List<MethodDeclaration> stepMethods = beanMethods.stream()
                            .filter(m -> isStepBean(m))
                            .toList();
                    List<MethodDeclaration> readerMethods = beanMethods.stream()
                            .filter(m -> isReaderBean(m))
                            .toList();
                    List<MethodDeclaration> processorMethods = beanMethods.stream()
                            .filter(m -> isProcessorBean(m))
                            .toList();
                    List<MethodDeclaration> writerMethods = beanMethods.stream()
                            .filter(m -> isWriterBean(m))
                            .toList();

                    for (MethodDeclaration jobMethod : jobMethods) {
                        Map<String, Object> job = buildJobDefinition(
                                jobMethod, stepMethods, readerMethods,
                                processorMethods, writerMethods, filePath, classDecl
                        );
                        jobs.add(job);
                    }

                    if (jobMethods.isEmpty() && (!readerMethods.isEmpty() || !writerMethods.isEmpty())) {
                        Map<String, Object> job = buildImplicitJob(
                                classDecl, readerMethods, processorMethods,
                                writerMethods, filePath
                        );
                        jobs.add(job);
                    }
                });

        return jobs;
    }

    private boolean hasBatchAnnotations(ClassOrInterfaceDeclaration classDecl) {
        return classDecl.getAnnotations().stream()
                .anyMatch(a -> {
                    String name = a.getNameAsString();
                    return name.equals("Configuration") || name.equals("EnableBatchProcessing");
                });
    }

    private boolean isBeanMethod(MethodDeclaration method) {
        return method.getAnnotationByName("Bean").isPresent();
    }

    private boolean isJobBean(MethodDeclaration method) {
        String returnType = method.getTypeAsString();
        if (returnType.equals("Job")) return true;
        String body = method.getBody().map(Object::toString).orElse("");
        return body.contains("jobBuilderFactory") || body.contains("JobBuilder");
    }

    private boolean isStepBean(MethodDeclaration method) {
        String returnType = method.getTypeAsString();
        if (returnType.equals("Step")) return true;
        String body = method.getBody().map(Object::toString).orElse("");
        return body.contains("stepBuilderFactory") || body.contains("StepBuilder");
    }

    private boolean isReaderBean(MethodDeclaration method) {
        String returnType = method.getTypeAsString();
        if (READER_TYPES.stream().anyMatch(returnType::contains)) return true;
        if (returnType.contains("ItemReader")) return true;
        String body = method.getBody().map(Object::toString).orElse("");
        return READER_TYPES.stream().anyMatch(body::contains);
    }

    private boolean isProcessorBean(MethodDeclaration method) {
        String returnType = method.getTypeAsString();
        if (PROCESSOR_TYPES.stream().anyMatch(returnType::contains)) return true;
        if (returnType.contains("ItemProcessor")) return true;
        String body = method.getBody().map(Object::toString).orElse("");
        return PROCESSOR_TYPES.stream().anyMatch(body::contains);
    }

    private boolean isWriterBean(MethodDeclaration method) {
        String returnType = method.getTypeAsString();
        if (WRITER_TYPES.stream().anyMatch(returnType::contains)) return true;
        if (returnType.contains("ItemWriter")) return true;
        String body = method.getBody().map(Object::toString).orElse("");
        return WRITER_TYPES.stream().anyMatch(body::contains);
    }

    private Map<String, Object> buildJobDefinition(
            MethodDeclaration jobMethod,
            List<MethodDeclaration> stepMethods,
            List<MethodDeclaration> readerMethods,
            List<MethodDeclaration> processorMethods,
            List<MethodDeclaration> writerMethods,
            String filePath,
            ClassOrInterfaceDeclaration classDecl) {

        Map<String, Object> job = new HashMap<>();
        job.put("job_name", extractBeanName(jobMethod));
        job.put("config_type", "java");
        job.put("config_file", filePath);

        String jobBody = jobMethod.getBody().map(Object::toString).orElse("");

        List<String> stepRefs = extractStepReferences(jobBody);
        List<Map<String, Object>> steps = new ArrayList<>();

        for (String stepRef : stepRefs) {
            Optional<MethodDeclaration> stepMethod = stepMethods.stream()
                    .filter(m -> m.getNameAsString().equals(stepRef))
                    .findFirst();

            Map<String, Object> step = buildStepDefinition(
                    stepRef, stepMethod.orElse(null),
                    readerMethods, processorMethods, writerMethods
            );
            steps.add(step);
        }

        if (steps.isEmpty() && !stepMethods.isEmpty()) {
            for (MethodDeclaration sm : stepMethods) {
                Map<String, Object> step = buildStepDefinition(
                        sm.getNameAsString(), sm,
                        readerMethods, processorMethods, writerMethods
                );
                steps.add(step);
            }
        }

        job.put("steps", steps);
        job.put("has_conditional_flow", detectConditionalFlow(jobBody));
        job.put("has_partitioning", detectPartitioning(jobBody));
        job.put("parameters", extractJobParameters(classDecl));
        job.put("listeners", extractListeners(classDecl));

        return job;
    }

    private Map<String, Object> buildImplicitJob(
            ClassOrInterfaceDeclaration classDecl,
            List<MethodDeclaration> readerMethods,
            List<MethodDeclaration> processorMethods,
            List<MethodDeclaration> writerMethods,
            String filePath) {

        String className = classDecl.getNameAsString();
        String jobName = deriveJobName(className);

        Map<String, Object> job = new HashMap<>();
        job.put("job_name", jobName);
        job.put("config_type", "java");
        job.put("config_file", filePath);

        Map<String, Object> step = new HashMap<>();
        step.put("step_name", jobName + "_step");
        step.put("is_tasklet", false);

        if (!readerMethods.isEmpty()) {
            step.put("reader", parseReaderMethod(readerMethods.get(0)));
        }
        if (!processorMethods.isEmpty()) {
            step.put("processor", parseProcessorMethod(processorMethods.get(0)));
        }
        if (!writerMethods.isEmpty()) {
            step.put("writer", parseWriterMethod(writerMethods.get(0)));
        }

        job.put("steps", List.of(step));
        job.put("has_conditional_flow", false);
        job.put("has_partitioning", false);
        job.put("parameters", List.of());
        job.put("listeners", List.of());

        return job;
    }

    private Map<String, Object> buildStepDefinition(
            String stepName,
            MethodDeclaration stepMethod,
            List<MethodDeclaration> readerMethods,
            List<MethodDeclaration> processorMethods,
            List<MethodDeclaration> writerMethods) {

        Map<String, Object> step = new HashMap<>();
        step.put("step_name", stepName);

        if (stepMethod == null) {
            step.put("is_tasklet", false);
            return step;
        }

        String stepBody = stepMethod.getBody().map(Object::toString).orElse("");

        boolean isTasklet = stepBody.contains(".tasklet(") && !stepBody.contains(".chunk(");
        step.put("is_tasklet", isTasklet);

        if (isTasklet) {
            step.put("tasklet_class", extractTaskletRef(stepBody));
            return step;
        }

        step.put("chunk_size", extractChunkSize(stepBody));
        step.put("error_handling", extractErrorHandling(stepBody));

        String readerRef = extractComponentRef(stepBody, "reader");
        String processorRef = extractComponentRef(stepBody, "processor");
        String writerRef = extractComponentRef(stepBody, "writer");

        MethodDeclaration readerMethod = findMethodByName(readerMethods, readerRef);
        MethodDeclaration procMethod = findMethodByName(processorMethods, processorRef);
        MethodDeclaration writerMethod = findMethodByName(writerMethods, writerRef);

        if (readerMethod == null && !readerMethods.isEmpty()) readerMethod = readerMethods.get(0);
        if (procMethod == null && !processorMethods.isEmpty()) procMethod = processorMethods.get(0);
        if (writerMethod == null && !writerMethods.isEmpty()) writerMethod = writerMethods.get(0);

        if (readerMethod != null) step.put("reader", parseReaderMethod(readerMethod));
        if (procMethod != null) step.put("processor", parseProcessorMethod(procMethod));
        if (writerMethod != null) step.put("writer", parseWriterMethod(writerMethod));

        return step;
    }

    private Map<String, Object> parseReaderMethod(MethodDeclaration method) {
        Map<String, Object> reader = new HashMap<>();
        reader.put("class_name", method.getNameAsString());

        String returnType = method.getTypeAsString();
        String body = method.getBody().map(Object::toString).orElse("");

        String readerType = "CustomItemReader";
        String sourceType = "UNKNOWN";
        boolean customLogic = true;

        for (String rt : READER_TYPES) {
            if (returnType.contains(rt) || body.contains(rt)) {
                readerType = rt;
                sourceType = READER_SOURCE_MAP.getOrDefault(rt, "UNKNOWN");
                customLogic = false;
                break;
            }
        }

        reader.put("reader_type", readerType);
        reader.put("source_type", sourceType);
        reader.put("custom_logic", customLogic);
        reader.put("properties", extractProperties(method));
        reader.put("return_type_full", returnType);

        return reader;
    }

    private Map<String, Object> parseProcessorMethod(MethodDeclaration method) {
        Map<String, Object> processor = new HashMap<>();
        processor.put("class_name", method.getNameAsString());

        String returnType = method.getTypeAsString();
        String body = method.getBody().map(Object::toString).orElse("");

        String procType = "CustomItemProcessor";
        for (String pt : PROCESSOR_TYPES) {
            if (returnType.contains(pt) || body.contains(pt)) {
                procType = pt;
                break;
            }
        }

        processor.put("processor_type", procType);
        processor.put("return_type_full", returnType);

        boolean hasLambda = method.findAll(LambdaExpr.class).size() > 0;
        processor.put("has_lambda", hasLambda);

        Set<String> externalCalls = new HashSet<>();
        method.findAll(MethodCallExpr.class).forEach(call -> {
            String scope = call.getScope().map(Object::toString).orElse("");
            if (scope.endsWith("Service") || scope.endsWith("Client")
                    || scope.endsWith("Repository") || scope.equals("restTemplate")
                    || scope.equals("webClient")) {
                externalCalls.add(scope + "." + call.getNameAsString());
            }
        });
        processor.put("external_calls", new ArrayList<>(externalCalls));

        boolean hasBusinessLogic = !externalCalls.isEmpty()
                || body.contains("if ")
                || body.contains("switch ")
                || body.contains(".stream()")
                || hasLambda;
        processor.put("has_business_logic", hasBusinessLogic);

        return processor;
    }

    private Map<String, Object> parseWriterMethod(MethodDeclaration method) {
        Map<String, Object> writer = new HashMap<>();
        writer.put("class_name", method.getNameAsString());

        String returnType = method.getTypeAsString();
        String body = method.getBody().map(Object::toString).orElse("");

        String writerType = "CustomItemWriter";
        String targetType = "UNKNOWN";
        boolean customLogic = true;

        for (String wt : WRITER_TYPES) {
            if (returnType.contains(wt) || body.contains(wt)) {
                writerType = wt;
                targetType = WRITER_TARGET_MAP.getOrDefault(wt, "UNKNOWN");
                customLogic = false;
                break;
            }
        }

        writer.put("writer_type", writerType);
        writer.put("target_type", targetType);
        writer.put("custom_logic", customLogic);
        writer.put("properties", extractProperties(method));
        writer.put("return_type_full", returnType);

        boolean hasLambda = method.findAll(LambdaExpr.class).size() > 0;
        writer.put("has_lambda", hasLambda);

        return writer;
    }

    private String extractBeanName(MethodDeclaration method) {
        Optional<AnnotationExpr> beanAnn = method.getAnnotationByName("Bean");
        if (beanAnn.isPresent()) {
            String annStr = beanAnn.get().toString();
            if (annStr.contains("\"")) {
                int start = annStr.indexOf('"') + 1;
                int end = annStr.indexOf('"', start);
                if (end > start) return annStr.substring(start, end);
            }
        }
        return method.getNameAsString();
    }

    private List<String> extractStepReferences(String jobBody) {
        List<String> refs = new ArrayList<>();
        String[] patterns = {".start(", ".next(", ".flow("};
        for (String pattern : patterns) {
            int idx = 0;
            while ((idx = jobBody.indexOf(pattern, idx)) != -1) {
                int start = idx + pattern.length();
                int end = jobBody.indexOf("(", start);
                if (end > start) {
                    String ref = jobBody.substring(start, end).trim();
                    if (!ref.isEmpty() && !refs.contains(ref)) {
                        refs.add(ref);
                    }
                }
                idx = start;
            }
        }
        return refs;
    }

    private String extractComponentRef(String stepBody, String componentType) {
        String pattern = "." + componentType + "(";
        int idx = stepBody.indexOf(pattern);
        if (idx == -1) return null;
        int start = idx + pattern.length();
        int end = stepBody.indexOf("(", start);
        if (end > start) {
            return stepBody.substring(start, end).trim();
        }
        return null;
    }

    private int extractChunkSize(String stepBody) {
        int idx = stepBody.indexOf("chunk");
        if (idx == -1) return 0;
        String rest = stepBody.substring(idx);
        StringBuilder num = new StringBuilder();
        boolean foundDigit = false;
        for (char c : rest.toCharArray()) {
            if (Character.isDigit(c)) {
                num.append(c);
                foundDigit = true;
            } else if (foundDigit) {
                break;
            }
        }
        try {
            return Integer.parseInt(num.toString());
        } catch (NumberFormatException e) {
            return 0;
        }
    }

    private Map<String, Object> extractErrorHandling(String stepBody) {
        Map<String, Object> eh = new HashMap<>();
        eh.put("skip_policy", stepBody.contains("skipLimit(") || stepBody.contains(".skip("));
        eh.put("retry_policy", stepBody.contains("retryLimit(") || stepBody.contains(".retry("));

        int skipLimit = extractIntParam(stepBody, "skipLimit(");
        int retryLimit = extractIntParam(stepBody, "retryLimit(");
        eh.put("skip_limit", skipLimit);
        eh.put("retry_limit", retryLimit);

        List<String> skippable = extractClassReferences(stepBody, ".skip(");
        List<String> retryable = extractClassReferences(stepBody, ".retry(");
        eh.put("skippable_exceptions", skippable);
        eh.put("retryable_exceptions", retryable);

        return eh;
    }

    private int extractIntParam(String body, String pattern) {
        int idx = body.indexOf(pattern);
        if (idx == -1) return 0;
        int start = idx + pattern.length();
        StringBuilder num = new StringBuilder();
        for (int i = start; i < body.length(); i++) {
            char c = body.charAt(i);
            if (Character.isDigit(c)) num.append(c);
            else if (!num.isEmpty()) break;
        }
        try {
            return Integer.parseInt(num.toString());
        } catch (NumberFormatException e) {
            return 0;
        }
    }

    private List<String> extractClassReferences(String body, String pattern) {
        List<String> refs = new ArrayList<>();
        int idx = 0;
        while ((idx = body.indexOf(pattern, idx)) != -1) {
            int start = idx + pattern.length();
            int end = body.indexOf(".class", start);
            if (end > start) {
                String ref = body.substring(start, end).trim();
                if (!ref.isEmpty()) refs.add(ref);
            }
            idx = start + 1;
        }
        return refs;
    }

    private String extractTaskletRef(String stepBody) {
        int idx = stepBody.indexOf(".tasklet(");
        if (idx == -1) return "";
        int start = idx + 9;
        int end = stepBody.indexOf(")", start);
        if (end > start) {
            String ref = stepBody.substring(start, end).trim();
            if (ref.endsWith("()")) ref = ref.substring(0, ref.length() - 2);
            return ref;
        }
        return "";
    }

    private boolean detectConditionalFlow(String jobBody) {
        return jobBody.contains(".on(") || jobBody.contains("JobExecutionDecider")
                || jobBody.contains("decider(") || jobBody.contains(".split(")
                || jobBody.contains("FlowBuilder");
    }

    private boolean detectPartitioning(String jobBody) {
        return jobBody.contains("partitioner(") || jobBody.contains("Partitioner")
                || jobBody.contains("gridSize") || jobBody.contains("TaskExecutor");
    }

    private List<String> extractJobParameters(ClassOrInterfaceDeclaration classDecl) {
        Set<String> params = new HashSet<>();
        String source = classDecl.toString();

        String[] patterns = {
                "jobParameters.getString(\"", "jobParameters.getLong(\"",
                "jobParameters.getDouble(\"", "jobParameters.getDate(\""
        };
        for (String pattern : patterns) {
            int idx = 0;
            while ((idx = source.indexOf(pattern, idx)) != -1) {
                int start = idx + pattern.length();
                int end = source.indexOf("\"", start);
                if (end > start) params.add(source.substring(start, end));
                idx = start + 1;
            }
        }

        return new ArrayList<>(params);
    }

    private List<Map<String, String>> extractListeners(ClassOrInterfaceDeclaration classDecl) {
        List<Map<String, String>> listeners = new ArrayList<>();
        classDecl.getMethods().stream()
                .filter(this::isBeanMethod)
                .filter(m -> {
                    String type = m.getTypeAsString();
                    return type.contains("Listener");
                })
                .forEach(m -> {
                    Map<String, String> listener = new HashMap<>();
                    listener.put("class_name", m.getNameAsString());
                    listener.put("listener_type", m.getTypeAsString());
                    listeners.add(listener);
                });
        return listeners;
    }

    private Map<String, String> extractProperties(MethodDeclaration method) {
        Map<String, String> props = new HashMap<>();

        method.findAll(MethodCallExpr.class).forEach(call -> {
            String name = call.getNameAsString();
            if (name.startsWith("set") || name.equals("sql") || name.equals("resource")) {
                call.getArguments().forEach(arg -> {
                    if (arg instanceof StringLiteralExpr) {
                        props.put(name, ((StringLiteralExpr) arg).getValue());
                    }
                });
            }
        });

        return props;
    }

    private MethodDeclaration findMethodByName(List<MethodDeclaration> methods, String name) {
        if (name == null) return null;
        return methods.stream()
                .filter(m -> m.getNameAsString().equals(name))
                .findFirst()
                .orElse(null);
    }

    private String deriveJobName(String className) {
        String name = className
                .replaceAll("Config$", "")
                .replaceAll("Configuration$", "");
        StringBuilder result = new StringBuilder();
        for (int i = 0; i < name.length(); i++) {
            char c = name.charAt(i);
            if (Character.isUpperCase(c) && i > 0) {
                result.append('_');
            }
            result.append(Character.toLowerCase(c));
        }
        if (!result.toString().endsWith("_job")) {
            result.append("_job");
        }
        return result.toString();
    }
}
