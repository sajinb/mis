package com.hr.mis.controller;

import com.hr.mis.service.FrontendMetadataService;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
import org.springframework.boot.test.mock.mockito.MockBean;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;

import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

@WebMvcTest(MetadataController.class)
public class MetadataControllerTest {

    @Autowired
    private MockMvc mockMvc;

    @MockBean
    private FrontendMetadataService frontendMetadataService;

    @Test
    public void testGetUiMetadata() throws Exception {
        String mockMetadata = "[{\"id\":\"/api/employees\",\"httpMethod\":\"POST\"}]";
        
        when(frontendMetadataService.fetchUiMetadata()).thenReturn(mockMetadata);

        mockMvc.perform(get("/api/metadata/ui"))
                .andExpect(status().isOk())
                .andExpect(content().contentType(MediaType.APPLICATION_JSON))
                .andExpect(content().string(mockMetadata));
    }
}
