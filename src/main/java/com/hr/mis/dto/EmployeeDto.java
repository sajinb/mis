package com.hr.mis.dto;

import jakarta.validation.constraints.*;
import java.math.BigDecimal;
import java.time.LocalDate;

public class EmployeeDto {

    private Long id;

    @NotBlank
    @Size(max = 100)
    private String firstName;

    @NotBlank
    @Size(max = 100)
    private String lastName;

    @Size(max = 150)
    private String projectName;

    @NotBlank
    @Email
    @Size(max = 255)
    private String email;

    @Size(max = 100)
    private String position;

    private BigDecimal salary;

    private LocalDate hiredDate;

    @Size(max = 300)
    private String address;

    // No-args constructor
    public EmployeeDto() {}

    // All-args constructor
    public EmployeeDto(Long id, String firstName, String lastName, String projectName,
                       String email, String position, BigDecimal salary,
                       LocalDate hiredDate, String address) {
        this.id = id;
        this.firstName = firstName;
        this.lastName = lastName;
        this.projectName = projectName;
        this.email = email;
        this.position = position;
        this.salary = salary;
        this.hiredDate = hiredDate;
        this.address = address;
    }

    // Getters and Setters
    public Long getId() { return id; }
    public void setId(Long id) { this.id = id; }

    public String getFirstName() { return firstName; }
    public void setFirstName(String firstName) { this.firstName = firstName; }

    public String getLastName() { return lastName; }
    public void setLastName(String lastName) { this.lastName = lastName; }

    public String getProjectName() { return projectName; }
    public void setProjectName(String projectName) { this.projectName = projectName; }

    public String getEmail() { return email; }
    public void setEmail(String email) { this.email = email; }

    public String getPosition() { return position; }
    public void setPosition(String position) { this.position = position; }

    public BigDecimal getSalary() { return salary; }
    public void setSalary(BigDecimal salary) { this.salary = salary; }

    public LocalDate getHiredDate() { return hiredDate; }
    public void setHiredDate(LocalDate hiredDate) { this.hiredDate = hiredDate; }

    public String getAddress() { return address; }
    public void setAddress(String address) { this.address = address; }
}
