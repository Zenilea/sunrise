use quote::quote;
use std::{env, fs, path::PathBuf};

fn main() {
    println!("cargo:rerun-if-changed=build.rs");
    let sig = syn::parse_quote!(fn proof(text: &str, count: u32, nested: Nested) -> bool);
    let shape = point_shape::shape(quote!(free, api(Nested = "Nested")), &sig)
        .expect("fixture signature is eligible for API points");
    assert!(shape.api());
    assert!(shape.borrows());
    let record = shape.record_item("fixture::proof");
    let mut output = String::new();
    output.push_str(
        &quote! {
            pub mod original {
                #[derive(::mod_api::Wire)]
                pub struct Child { pub value: bool }
                #[derive(::mod_api::Wire)]
                pub struct Nested { pub child: Child }
                #record
            }
        }
        .to_string(),
    );
    fs::write(
        PathBuf::from(env::var_os("OUT_DIR").unwrap()).join("records.rs"),
        output,
    )
    .unwrap();
}
