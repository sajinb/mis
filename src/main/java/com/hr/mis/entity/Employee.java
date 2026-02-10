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
}
