# coding: utf-8
lib = File.expand_path('../lib', __FILE__)
$LOAD_PATH.unshift(lib) unless $LOAD_PATH.include?(lib)
require 'gel/version'

Gem::Specification.new do |spec|
  spec.name          = "gel"
  spec.version       = Gel::VERSION
  spec.authors       = ["Nathan Lilienthal"]
  spec.email         = ["nathan@nixpulvis.com"]
  spec.description   = %q{Simple OpenGL Graphics Library.}
  spec.summary       = %q{Simple OpenGL Graphics Library.}
  spec.homepage      = ""
  spec.license       = "MIT"

  spec.files         = `git ls-files`.split($/)
  spec.executables   = spec.files.grep(%r{^bin/}) { |f| File.basename(f) }
  spec.test_files    = spec.files.grep(%r{^(test|spec|features)/})
  spec.require_paths = ["lib"]

  spec.add_dependency "opengl"

  spec.add_development_dependency "bundler", "~> 1.3"
  spec.add_development_dependency "bundler", "~> 1.3"
end
