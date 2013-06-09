# coding: utf-8
lib = File.expand_path('../lib', __FILE__)
$LOAD_PATH.unshift(lib) unless $LOAD_PATH.include?(lib)

Gem::Specification.new do |spec|
  spec.name          = "serial_monitor"
  spec.version       = "0.0.1"
  spec.authors       = ["Nathan Lilienthal"]
  spec.email         = ["nathan@nixpulvis.com"]
  spec.description   = %q{Read Serial.}
  spec.summary       = %q{Read Serial.}
  spec.homepage      = ""
  spec.license       = "MIT"

  spec.files         = `git ls-files`.split($/)
  spec.executables   = spec.files.grep(%r{^bin/}) { |f| File.basename(f) }
  spec.test_files    = spec.files.grep(%r{^(test|spec|features)/})
  spec.require_paths = ["lib"]

  spec.add_dependency "serialport"

  spec.add_development_dependency "bundler", "~> 1.3"
  spec.add_development_dependency "bundler", "~> 1.3"
end
