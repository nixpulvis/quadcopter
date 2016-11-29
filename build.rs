extern crate gcc;

fn main() {
    // TODO: Use latexmk directly.
    make::compile_library("spec.pdf", "doc");
    gcc::compile_library("libhello.a", &["src/hello.c"]);
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
