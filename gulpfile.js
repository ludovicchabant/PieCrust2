'use strict';

var gulp = require('gulp'),
    util = require('gulp-util'),
    sass = require('gulp-sass'),
    sourcemaps = require('gulp-sourcemaps'),
    rename = require('gulp-rename'),
    cssnano = require('gulp-cssnano'),
    concat = require('gulp-concat'),
    uglify = require('gulp-uglify');

// Stylesheets
gulp.task('sass', function() {
    return gulp.src('piecrust/admin/assets/sass/**/*.scss')
        //.pipe(sourcemaps.init())
        .pipe(sass({
            errLogToConsole: true,
            outputStyle: 'compressed',
            includePaths: [
                'node_modules/bootstrap/scss',
                'node_modules/open-iconic/font/css']}))
        .pipe(cssnano())
        //.pipe(sourcemaps.write())
        .pipe(rename({suffix: '.min'}))
        .pipe(gulp.dest('piecrust/admin/static/css'));
});
gulp.task('sass:watch', function() {
    return gulp.watch('piecrust/admin/assets/sass/**/*.scss', ['sass']);
});

// Javascript
gulp.task('js', function() {
    return gulp.src([
            'node_modules/jquery/dist/jquery.min.js',
            'node_modules/bootstrap/dist/js/bootstrap.min.js',
            'node_modules/timeago/jquery.timeago.js',
            'piecrust/admin/assets/js/**/*.js'
            ])
        .pipe(sourcemaps.init())
        .pipe(concat('foodtruck.js'))
        //.pipe(uglify())
        .pipe(sourcemaps.write())
        .pipe(rename({suffix: '.min'}))
        .pipe(gulp.dest('piecrust/admin/static/js'));
});
gulp.task('js:watch', function() {
    return gulp.watch('piecrust/admin/assets/js/**/*.js', ['js']);
});

// Fonts/images
gulp.task('fonts', function() {
    return gulp.src([
            'node_modules/open-iconic/font/fonts/*'
        ])
        .pipe(gulp.dest('piecrust/admin/static/fonts'));
});

gulp.task('images', function() {
    return gulp.src([
            'piecrust/admin/assets/img/*'
        ])
        .pipe(gulp.dest('piecrust/admin/static/img'));
});

// Launch tasks
gulp.task('default', function() {
    gulp.start(['sass', 'js', 'fonts', 'images']);
});

gulp.task('watch', function() {
    gulp.start(['sass:watch', 'js:watch']);
});


