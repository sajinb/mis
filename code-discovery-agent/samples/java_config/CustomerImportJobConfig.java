package com.example.batch.config;

import org.springframework.batch.core.Job;
import org.springframework.batch.core.Step;
import org.springframework.batch.core.configuration.annotation.EnableBatchProcessing;
import org.springframework.batch.core.configuration.annotation.JobBuilderFactory;
import org.springframework.batch.core.configuration.annotation.StepBuilderFactory;
import org.springframework.batch.core.configuration.annotation.StepScope;
import org.springframework.batch.item.database.JdbcBatchItemWriter;
import org.springframework.batch.item.file.FlatFileItemReader;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Configuration
@EnableBatchProcessing
public class CustomerImportJobConfig {

    @Autowired
    private JobBuilderFactory jobBuilderFactory;

    @Autowired
    private StepBuilderFactory stepBuilderFactory;

    @Bean
    public Job customerImportJob() {
        return jobBuilderFactory.get("customerImportJob")
                .start(importStep())
                .build();
    }

    @Bean
    public Step importStep() {
        return stepBuilderFactory.get("importStep")
                .<CustomerInput, CustomerOutput>chunk(100)
                .reader(customerReader())
                .processor(customerProcessor())
                .writer(customerWriter())
                .faultTolerant()
                .skipLimit(10)
                .skip(ValidationException.class)
                .build();
    }

    @Bean
    @StepScope
    public FlatFileItemReader<CustomerInput> customerReader() {
        FlatFileItemReader<CustomerInput> reader = new FlatFileItemReader<>();
        reader.setResource(new ClassPathResource("input/customers.csv"));
        reader.setLineMapper(new DefaultLineMapper<>());
        return reader;
    }

    @Bean
    public CustomerProcessor customerProcessor() {
        return new CustomerProcessor();
    }

    @Bean
    public JdbcBatchItemWriter<CustomerOutput> customerWriter() {
        JdbcBatchItemWriter<CustomerOutput> writer = new JdbcBatchItemWriter<>();
        writer.setSql("INSERT INTO customers (id, name, email, status) VALUES (:id, :name, :email, :status)");
        return writer;
    }
}
