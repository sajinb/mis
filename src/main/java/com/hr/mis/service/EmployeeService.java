package com.hr.mis.service;

import com.hr.mis.dto.EmployeeDto;
import com.hr.mis.dto.EmployeeRequest;
import com.hr.mis.entity.Employee;
import com.hr.mis.repo.EmployeeRepository;
import jakarta.persistence.EntityNotFoundException;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;
import java.util.stream.Collectors;

@Service
public class EmployeeService {

    private final EmployeeRepository employeeRepository;

    public EmployeeService(EmployeeRepository employeeRepository) {
        this.employeeRepository = employeeRepository;
    }

    @Transactional
    public EmployeeDto create(EmployeeRequest request) {
        Employee employee = new Employee();
        mapRequestToEntity(request, employee);
        return toDto(employeeRepository.save(employee));
    }

    @Transactional
    public EmployeeDto update(Long id, EmployeeRequest request) {
        Employee employee = employeeRepository.findById(id)
                .orElseThrow(() -> new EntityNotFoundException("Employee not found with id: " + id));
        mapRequestToEntity(request, employee);
        return toDto(employeeRepository.save(employee));
    }

    public List<EmployeeDto> findAll() {
        return employeeRepository.findAll()
                .stream()
                .map(this::toDto)
                .collect(Collectors.toList());
    }

    public EmployeeDto findById(Long id) {
        Employee employee = employeeRepository.findById(id)
                .orElseThrow(() -> new EntityNotFoundException("Employee not found with id: " + id));
        return toDto(employee);
    }

    private void mapRequestToEntity(EmployeeRequest request, Employee employee) {
        employee.setFirstName(request.getFirstName());
        employee.setLastName(request.getLastName());
        employee.setProjectName(request.getProjectName());
        employee.setEmail(request.getEmail());
        employee.setPosition(request.getPosition());
        employee.setSalary(request.getSalary());
        employee.setHiredDate(request.getHiredDate());
        employee.setAddress(request.getAddress());
    }

    private EmployeeDto toDto(Employee employee) {
        return new EmployeeDto(
                employee.getId(),
                employee.getFirstName(),
                employee.getLastName(),
                employee.getProjectName(),
                employee.getEmail(),
                employee.getPosition(),
                employee.getSalary(),
                employee.getHiredDate(),
                employee.getAddress()
        );
    }
}
