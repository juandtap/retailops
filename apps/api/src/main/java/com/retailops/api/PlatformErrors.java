package com.retailops.api;

import org.springframework.context.annotation.Profile;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.http.converter.HttpMessageNotReadableException;
import org.springframework.web.method.annotation.MethodArgumentTypeMismatchException;
import org.springframework.web.bind.MissingServletRequestParameterException;
import static com.retailops.api.AppDtos.*;

@RestControllerAdvice @Profile("integrated")
class PlatformErrors {
    @ExceptionHandler(AppFailure.class) ResponseEntity<ApiError> expected(AppFailure e){return ResponseEntity.status(e.status).body(new ApiError(e.code,e.getMessage()));}
    @ExceptionHandler({MethodArgumentNotValidException.class,HttpMessageNotReadableException.class,MethodArgumentTypeMismatchException.class,MissingServletRequestParameterException.class})
    ResponseEntity<ApiError> invalid(Exception e){return ResponseEntity.badRequest().body(new ApiError("INVALID_REQUEST","Parámetros inválidos o campos no permitidos"));}
    @ExceptionHandler(Exception.class) ResponseEntity<ApiError> unexpected(Exception e){return ResponseEntity.internalServerError().body(new ApiError("INTERNAL_ERROR","No se pudo completar la solicitud"));}
}
