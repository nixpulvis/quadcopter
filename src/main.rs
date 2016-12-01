#[macro_use]
extern crate clap;

use clap::ArgMatches;

fn main() {
    let matches = clap_app!(quadcopter =>
        (version: "0.0.1")
        (about: "Fly.")
        // (@arg CONFIG: -c --config +takes_value "Sets a custom config file")
        // (@arg verbose: -v --verbose "Print test information verbosely")

        (@subcommand safety =>
            (about: "enable or disable the quadcopter's safety mechanism.")
            (version: "0.0.1")
            (@arg set: +required "set the quadcopter's saftey to \"on\" or \"off\"."))

        (@subcommand power =>
            (about: "optimistically set the motor output power.")
            (version: "0.0.1")
            (@arg percent: +required "the percent value to set the quadcopter's power to."))

        (@subcommand test =>
            (about: "run the quadcopter system tests.")
            (version: "0.0.1"))

    ).get_matches();

    match matches.subcommand() {
        ("safety", args) => safety(args.unwrap()),
        ("power", args)  => power(args.unwrap()),
        ("test", args)   => test(args.unwrap()),
        _ => unreachable!(),
    }
}

// Set the quadcopter's saftey settings based on the given user arguments.
fn safety<'a>(args: &ArgMatches<'a>) {
    match args.value_of("set") {
        Some("on") => println!("setting the saftey to ON"),
        Some("off") => println!("setting the saftey to OFF"),
        _ => panic!("bad value for saftey setting")
    }
}

// Set the quadcopter's saftey settings based on the given user arguments.
fn power<'a>(args: &ArgMatches<'a>) {
    match value_t!(args, "percent", f64) {
        Ok(value) if value <= 100f64 => println!("attempting to set the power to {}%.", value),
        _ => panic!("bad value for percent")
    }
}

// Run the quadcopter's self test.
fn test<'a>(_args: &ArgMatches<'a>) {
    println!("testing motor A");
    println!("testing motor B");
    println!("testing motor C");
    println!("testing motor D");
    println!("testing red light");
    println!("testing greed light");
    println!("testing blue light");
    println!("testing spotlight");
}
