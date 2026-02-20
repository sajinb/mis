package com.example.batch.config;

import org.springframework.batch.core.Job;
import org.springframework.batch.core.Step;
import org.springframework.batch.core.configuration.annotation.EnableBatchProcessing;
import org.springframework.batch.core.configuration.annotation.JobBuilderFactory;
import org.springframework.batch.core.configuration.annotation.StepBuilderFactory;
import org.springframework.batch.item.ItemProcessor;
import org.springframework.batch.item.ItemWriter;
import org.springframework.batch.item.database.JdbcCursorItemReader;
import org.springframework.batch.item.database.JdbcBatchItemWriter;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Configuration
@EnableBatchProcessing
public class OrderProcessingJobConfig {

    @Autowired
    private JobBuilderFactory jobBuilderFactory;

    @Autowired
    private StepBuilderFactory stepBuilderFactory;

    @Autowired
    private OrderValidationService orderValidationService;

    @Autowired
    private PricingService pricingService;

    @Bean
    public Job orderProcessingJob() {
        return jobBuilderFactory.get("orderProcessingJob")
                .start(validateOrdersStep())
                .next(calculateTotalsStep())
                .build();
    }

    @Bean
    public Step validateOrdersStep() {
        return stepBuilderFactory.get("validateOrdersStep")
                .<RawOrder, ValidatedOrder>chunk(50)
                .reader(orderReader())
                .processor(orderValidationProcessor())
                .writer(validatedOrderWriter())
                .faultTolerant()
                .retryLimit(3)
                .retry(TransientDataAccessException.class)
                .skipLimit(5)
                .skip(InvalidOrderException.class)
                .build();
    }

    @Bean
    public Step calculateTotalsStep() {
        return stepBuilderFactory.get("calculateTotalsStep")
                .<ValidatedOrder, ProcessedOrder>chunk(100)
                .reader(validatedOrderReader())
                .writer(orderTotalWriter())
                .build();
    }

    @Bean
    public JdbcCursorItemReader<RawOrder> orderReader() {
        JdbcCursorItemReader<RawOrder> reader = new JdbcCursorItemReader<>();
        reader.setSql("SELECT id, customer_id, product_id, quantity, order_date FROM raw_orders WHERE status = 'NEW'");
        return reader;
    }

    @Bean
    public ItemProcessor<RawOrder, ValidatedOrder> orderValidationProcessor() {
        return order -> {
            if (!orderValidationService.validate(order)) {
                return null;
            }
            ValidatedOrder validated = new ValidatedOrder();
            validated.setId(order.getId());
            validated.setCustomerId(order.getCustomerId());
            validated.setProductId(order.getProductId());
            validated.setQuantity(order.getQuantity());
            validated.setValid(true);
            return validated;
        };
    }

    @Bean
    public JdbcBatchItemWriter<ValidatedOrder> validatedOrderWriter() {
        JdbcBatchItemWriter<ValidatedOrder> writer = new JdbcBatchItemWriter<>();
        writer.setSql("UPDATE orders SET status = 'VALIDATED', validated_at = NOW() WHERE id = :id");
        return writer;
    }

    @Bean
    public JdbcCursorItemReader<ValidatedOrder> validatedOrderReader() {
        JdbcCursorItemReader<ValidatedOrder> reader = new JdbcCursorItemReader<>();
        reader.setSql("SELECT * FROM orders WHERE status = 'VALIDATED'");
        return reader;
    }

    @Bean
    public ItemWriter<ProcessedOrder> orderTotalWriter() {
        return items -> {
            for (ProcessedOrder item : items) {
                // THIS IS PROCESSOR LOGIC IN THE WRITER!
                double unitPrice = pricingService.getPrice(item.getProductId());
                double total = unitPrice * item.getQuantity();
                double tax = total * 0.08;
                item.setUnitPrice(unitPrice);
                item.setTotal(total);
                item.setTax(tax);
                item.setGrandTotal(total + tax);
                item.setStatus("PROCESSED");

                if (total > 10000) {
                    item.setRequiresApproval(true);
                    item.setApprovalLevel("MANAGER");
                } else if (total > 50000) {
                    item.setRequiresApproval(true);
                    item.setApprovalLevel("DIRECTOR");
                }

                jdbcTemplate.update(
                    "UPDATE orders SET total = ?, tax = ?, grand_total = ?, status = ? WHERE id = ?",
                    item.getGrandTotal(), item.getTax(), item.getGrandTotal(),
                    item.getStatus(), item.getId()
                );
            }
        };
    }
}
