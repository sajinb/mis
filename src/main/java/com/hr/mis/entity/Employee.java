package com.hr.mis.entity;

import jakarta.persistence.*;
import jakarta.validation.constraints.*;
import java.math.BigDecimal;
import java.time.LocalDate;

@Entity
@Table(name = "employees")
public class Employee {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @NotBlank
    @Size(max = 100)
    @Column(name = "first_name", nullable = false, length = 100)
    private String firstName;

    @NotBlank
    @Size(max = 100)
    @Column(name = "last_name", nullable = false, length = 100)
    private String lastName;

    @Size(max = 150)
    @Column(name = "project_name", length = 150)
    private String projectName;

    @NotBlank
    @Email
    @Size(max = 255)
    @Column(name = "email", nullable = false, unique = true, length = 255)
    private String email;

    @Size(max = 100)
    @Column(name = "position", length = 100)
    private String position;

    @Column(name = "salary")
    private BigDecimal salary;

    @Column(name = "hired_date")
    private LocalDate hiredDate;

    @Column(name = "address", nullable = true, length = 300)
    private String address;

    // No-args constructor
    public Employee() {}

    // All-args constructor
    public Employee(Long id, String firstName, String lastName, String projectName,
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
