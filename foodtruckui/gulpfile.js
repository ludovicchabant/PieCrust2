'use strict';

var gulp = require('gulp'),
    util = require('gulp-util'),
    sass = require('gulp-sass'),
    sourcemaps = require('gulp-sourcemaps'),
    rename = require('gulp-rename'),
    minify = require('gulp-minify-css'),
    concat = require('gulp-concat'),
    uglify = require('gulp-uglify');

// Stylesheets
gulp.task('sass', function() {
    //util.log("Generating CSS");
    return gulp.src('assets/sass/**/*.scss')
        //.pipe(sourcemaps.init())
        .pipe(sass({
            errLogToConsole: true,
            outputStyle: 'compressed',
            includePaths: [
                'bower_components/bootstrap-sass/assets/stylesheets',
                'bower_components/Ionicons/scss']}))
        //.pipe(sourcemaps.write())
        .pipe(rename({suffix: '.min'}))
        .pipe(minify())
        .pipe(gulp.dest('../foodtruck/static/css'));
});
gulp.task('sass:watch', function() {
    return gulp.watch('assets/sass/**/*.scss', ['sass']);
});

// Javascript
gulp.task('js', function() {
    return gulp.src([
            'bower_components/jquery/dist/jquery.js',
            'bower_components/bootstrap-sass/assets/javascripts/bootstrap/alert.js',
            'bower_components/bootstrap-sass/assets/javascripts/bootstrap/button.js',
            'bower_components/bootstrap-sass/assets/javascripts/bootstrap/collapse.js',
            'bower_components/bootstrap-sass/assets/javascripts/bootstrap/dropdown.js',
            'bower_components/bootstrap-sass/assets/javascripts/bootstrap/tooltip.js',
            'bower_components/bootstrap-sass/assets/javascripts/bootstrap/transition.js',
            'assets/js/**/*.js'
            ])
        .pipe(sourcemaps.init())
        .pipe(concat('foodtruck.js'))
        .pipe(sourcemaps.write())
        .pipe(rename({suffix: '.min'}))
        //.pipe(uglify())
        .pipe(gulp.dest('../foodtruck/static/js'));
});
gulp.task('js:watch', function() {
    return gulp.watch('assets/js/**/*.js', ['js']);
});

// Fonts/images
gulp.task('fonts', function() {
    return gulp.src([
            'bower_components/bootstrap-sass/assets/fonts/bootstrap/*',
            'bower_components/Ionicons/fonts/*'
        ])
        .pipe(gulp.dest('../foodtruck/static/fonts'));
});

gulp.task('images', function() {
    return gulp.src([
            'bower_components/bootstrap-sass/assets/images/*',
            'assets/img/*'
        ])
        .pipe(gulp.dest('../foodtruck/static/img'));
});

// Launch tasks
gulp.task('default', function() {
    gulp.start(['sass', 'js', 'fonts', 'images']);
});

gulp.task('watch', function() {
    gulp.start(['sass:watch', 'js:watch']);
});

