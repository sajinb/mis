package com.hr.mis.service;

import org.springframework.http.HttpStatusCode;
import org.springframework.stereotype.Service;
import org.springframework.web.client.RestClient;
import org.springframework.web.server.ResponseStatusException;

@Service
public class FrontendMetadataService {

    private static final String FRONTEND_METADATA_URL = 
        "https://raw.githubusercontent.com/sajinb/frontend/main/src/meta/ui-metadata.json";

    private final RestClient restClient;

    public FrontendMetadataService(RestClient.Builder restClientBuilder) {
        this.restClient = restClientBuilder.build();
    }

    public String fetchUiMetadata() {
        return restClient.get()
                .uri(FRONTEND_METADATA_URL)
                .retrieve()
                .onStatus(HttpStatusCode::isError, (request, response) -> {
                    throw new ResponseStatusException(
                        response.getStatusCode(),
                        "Failed to fetch UI metadata from frontend repository"
                    );
                })
                .body(String.class);
    }
}
