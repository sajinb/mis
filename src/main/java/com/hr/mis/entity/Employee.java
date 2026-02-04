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
    @Size(max = 500)
    @Column(name = "first_name", nullable = false, length = 500)
    private String firstName;

    @NotBlank
    @Size(max = 150)
    @Column(name = "last_name", nullable = false, length = 150)
    private String lastName;

    @Email
    @NotBlank
    @Size(max = 254)
    @Column(name = "email", nullable = false, unique = true, length = 254)
    private String email;

    @Column(name = "position", length = 200)
    @Size(max = 200)
    private String position;

    @PositiveOrZero
    @Column(name = "salary", precision = 12, scale = 2)
    private BigDecimal salary;

    @Column(name = "hired_date")
    private LocalDate hiredDate;

    // Constructors
    public Employee() {
    }

    public Employee(String firstName, String lastName, String email, String position, BigDecimal salary, LocalDate hiredDate) {
        this.firstName = firstName;
        this.lastName = lastName;
        this.email = email;
        this.position = position;
        this.salary = salary;
        this.hiredDate = hiredDate;
    }

    // Getters and setters
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
