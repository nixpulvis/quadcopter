extern crate gcc;

fn main() {
    // TODO: Use latexmk directly.
    make::compile_library("spec.pdf", "hardware");
    gcc::compile_library("libhello.a", &["src/hello.c"]);
    avr_gcc::compile_library("libesc.a", "esc/src/esc.c");
}

mod make {
    use std::process::Command;

    pub fn compile_library(target: &str, directory: &str) {
        let exit = Command::new("make")
            .arg(target)
            .current_dir(directory)
            .status()
            .unwrap();
        assert!(exit.success());
    }
}

mod avr_gcc {
    use gcc;

    pub fn compile_library(target: &str, file: &str) {
        // TODO: ESC project.
        gcc::Config::new()
            .compiler("avr-gcc")
            .target("avr")
            .file(file)
            .define("F_CPU", Some("16000000UL"))
            .define("MMCU", Some("atmega328p"))
            .flag("-std=c99")
            .flag("-pedantic")
            .flag("-Wall")
            // .flag("-Werror")
            .include("/usr/local/avr/include")
            .include("/usr/local/Cellar/avr-libc/2.0.0/avr/include")
            .compile(target);
    }
}
