To update the `Employee` entity class with the new UI fields, we need to add the new fields with the appropriate JPA annotations and generate getters and setters for them. Here's the updated code:


package com.hr.mis.entity;

import javax.persistence.*;
import java.math.BigDecimal;
import java.time.LocalDate;

import jakarta.validation.constraints.*;

@Entity
@Table(name = "employees")
public class Employee {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @NotBlank
    @Size(max = 800)
    @Column(name = "first_name", length = 800, nullable = false)
    private String firstName;

    @NotBlank
    @Size(max = 150)
    @Column(name = "last_name", length = 150, nullable = false)
    private String lastName;

    @Size(max = 500)
    @Column(name = "project_name", length = 500)
    private String projectName;

    @NotBlank
    @Email
    @Size(max = 255)
    @Column(name = "email", length = 255, nullable = false)
    private String email;

    @Size(max = 200)
    @Column(name = "position", length = 200)
    private String position;

    @Column(name = "salary", precision = 15, scale = 2)
    private BigDecimal salary;

    @Column(name = "hired_date")
    private LocalDate hiredDate;

    // New fields
    @Size(max = 400)
    @Column(name = "address", length = 400)
    private String address;

    @Size(max = 500)
    @Column(name = "primary_skills", length = 500)
    private String primarySkills;

    public Employee() {
    }

    public Long getId() {
        return id;
    }

    public void setId(Long id) {
        this.id = id;
    }

    public String getFirstName() {
        return firstName;
    }

    public void setFirstName(String firstName) {
        this.firstName = firstName;
    }

    public String getLastName() {
        return lastName;
    }

    public void setLastName(String lastName) {
        this.lastName = lastName;
    }

    public String getProjectName() {
        return projectName;
    }

    public void setProjectName(String projectName) {
        this.projectName = projectName;
    }

    public String getEmail() {
        return email;
    }

    public void setEmail(String email) {
        this.email = email;
    }

    public String getPosition() {
        return position;
    }

    public void setPosition(String position) {
        this.position = position;
    }

    public BigDecimal getSalary() {
        return salary;
    }

    public void setSalary(BigDecimal salary) {
        this.salary = salary;
    }

    public LocalDate getHiredDate() {
        return hiredDate;
    }

    public void setHiredDate(LocalDate hiredDate) {
        this.hiredDate = hiredDate;
    }

    public String getAddress() {
        return address;
    }

    public void setAddress(String address) {
        this.address = address;
    }

    public String getPrimarySkills() {
        return primarySkills;
    }

    public void setPrimarySkills(String primarySkills) {
        this.primarySkills = primarySkills;
    }
}


### Changes Made:
1. Added a new field `address` with a maximum length of 400 characters.
2. Added a new field `primarySkills` with a maximum length of 500 characters.
3. Generated getters and setters for the new fields.