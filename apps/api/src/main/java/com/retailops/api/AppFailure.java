package com.retailops.api;

final class AppFailure extends RuntimeException {
    final int status;
    final String code;
    AppFailure(int status,String code,String message) {super(message);this.status=status;this.code=code;}
}
