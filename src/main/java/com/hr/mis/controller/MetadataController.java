package com.hr.mis.controller;

import com.hr.mis.service.FrontendMetadataService;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/metadata")
public class MetadataController {

    private final FrontendMetadataService frontendMetadataService;

    public MetadataController(FrontendMetadataService frontendMetadataService) {
        this.frontendMetadataService = frontendMetadataService;
    }

    @GetMapping("/ui")
    public ResponseEntity<String> getUiMetadata() {
        String metadata = frontendMetadataService.fetchUiMetadata();
        return ResponseEntity.ok()
                .contentType(MediaType.APPLICATION_JSON)
                .body(metadata);
    }
}
