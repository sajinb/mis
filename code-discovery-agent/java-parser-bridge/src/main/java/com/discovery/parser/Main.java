package com.discovery.parser;

import com.google.gson.Gson;
import com.google.gson.GsonBuilder;

import java.io.IOException;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.Map;

public class Main {

    public static void main(String[] args) throws IOException {
        if (args.length < 2) {
            System.err.println("Usage: java -jar java-parser-bridge.jar <command> <source-path>");
            System.err.println("Commands: analyze, detect-writer-logic, map-dependencies");
            System.exit(1);
        }

        String command = args[0];
        Path sourcePath = Paths.get(args[1]);
        Gson gson = new GsonBuilder().setPrettyPrinting().create();

        switch (command) {
            case "analyze":
                SpringBatchAnalyzer analyzer = new SpringBatchAnalyzer();
                var jobs = analyzer.analyzeDirectory(sourcePath);
                System.out.println(gson.toJson(Map.of("jobs", jobs)));
                break;

            case "detect-writer-logic":
                WriterLogicAnalyzer writerAnalyzer = new WriterLogicAnalyzer();
                var writerResults = writerAnalyzer.analyzeDirectory(sourcePath);
                System.out.println(gson.toJson(Map.of("writer_analysis", writerResults)));
                break;

            case "map-dependencies":
                DependencyAnalyzer depAnalyzer = new DependencyAnalyzer();
                var deps = depAnalyzer.analyzeDirectory(sourcePath);
                System.out.println(gson.toJson(Map.of("dependencies", deps)));
                break;

            default:
                System.err.println("Unknown command: " + command);
                System.exit(1);
        }
    }
}
