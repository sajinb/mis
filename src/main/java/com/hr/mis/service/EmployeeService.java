package com.hr.mis.service;

import com.hr.mis.entity.Employee;
import com.hr.mis.repository.EmployeeRepository;
import org.springframework.stereotype.Service;

import java.util.List;
import java.util.Optional;

@Service
public class EmployeeService {

    private final EmployeeRepository repository;

    public EmployeeService(EmployeeRepository repository) {
        this.repository = repository;
    }

    public Employee create(Employee employee) {
        // ensure id is null for create
        employee.setId(null);
        return repository.save(employee);
    }

    public Optional<Employee> update(Long id, Employee updated) {
        return repository.findById(id).map(existing -> {
            existing.setFirstName(updated.getFirstName());
            existing.setLastName(updated.getLastName());
            existing.setProjectName(updated.getProjectName());
            existing.setEmail(updated.getEmail());
            existing.setPosition(updated.getPosition());
            existing.setSalary(updated.getSalary());
            existing.setHiredDate(updated.getHiredDate());
            return repository.save(existing);
        });
    }

    public List<Employee> findAll() {
        return repository.findAll();
    }
}
