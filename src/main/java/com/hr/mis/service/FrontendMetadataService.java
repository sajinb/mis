package com.hr.mis.service;

import org.springframework.stereotype.Service;
import org.springframework.web.client.RestClient;

@Service
public class FrontendMetadataService {

    private static final String FRONTEND_METADATA_URL = 
        "https://raw.githubusercontent.com/sajinb/frontend/main/src/meta/ui-metadata.json";

    private final RestClient restClient;

    public FrontendMetadataService() {
        this.restClient = RestClient.create();
    }

    public String fetchUiMetadata() {
        return restClient.get()
                .uri(FRONTEND_METADATA_URL)
                .retrieve()
                .body(String.class);
    }
}
