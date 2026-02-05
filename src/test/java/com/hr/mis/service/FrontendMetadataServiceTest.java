package com.hr.mis.service;

import org.junit.jupiter.api.Test;
import org.springframework.web.client.RestClient;

import static org.junit.jupiter.api.Assertions.*;

public class FrontendMetadataServiceTest {

    @Test
    public void testFetchUiMetadata() {
        FrontendMetadataService service = new FrontendMetadataService(RestClient.builder());
        
        String metadata = service.fetchUiMetadata();
        
        assertNotNull(metadata, "Metadata should not be null");
        assertTrue(metadata.contains("\"id\":"), "Metadata should contain id field");
        assertTrue(metadata.contains("\"httpMethod\":"), "Metadata should contain httpMethod field");
        assertTrue(metadata.contains("/api/employees"), "Metadata should contain employees endpoint");
    }
}
