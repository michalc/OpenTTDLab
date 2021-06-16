use std::io::{Cursor, Seek, SeekFrom};
use wasm_bindgen::prelude::*;
use lzma_rs::xz_decompress;
use js_sys::Uint8Array;
use serde::{Serialize, Deserialize};
use std::collections::{VecDeque, HashMap};
use std::iter::FromIterator;


#[derive(Serialize, Deserialize, Debug)]
#[serde(untagged)]
enum Value {
    I8(i8),
    U8(u8),
    I16(i16),
    U16(u16),
    I32(i32),
    U32(u32),
    I64(i64),
    U64(u64),
    String(String),
    Struct(HashMap<String, Value>),
    List(Vec<Value>),
}


#[derive(Serialize, Deserialize, Debug, Default)]
struct Savegame {
    error: String,
    revision: u16,
    chunks: HashMap<String, HashMap<u32, Value>>,
}

#[wasm_bindgen()]
extern "C" {
    #[wasm_bindgen(js_namespace = console)]
    fn log(s: &str);
}

macro_rules! console_log {
    ($($t:tt)*) => (log(&format_args!($($t)*).to_string()))
}

fn read_uint8(data: &mut VecDeque<&u8>) -> u8 {
    if data.len() == 0 {
        panic!("End-of-file reached");
    }
    let byte = data.pop_front().unwrap();
    return *byte;
}

fn read_uint16(data: &mut VecDeque<&u8>) -> u16 {
    return (read_uint8(data) as u16) << 8 | read_uint8(data) as u16;
}

fn read_uint32(data: &mut VecDeque<&u8>) -> u32 {
    return (read_uint16(data) as u32) << 16 | read_uint16(data) as u32;
}

fn read_uint64(data: &mut VecDeque<&u8>) -> u64 {
    return (read_uint32(data) as u64) << 32 | read_uint32(data) as u64;
}

fn read_bytes(data: &mut VecDeque<&u8>, size: u32) -> VecDeque<u8> {
    let mut res: VecDeque<u8> = VecDeque::new();

    for _ in 0..size {
        res.push_back(read_uint8(data));
    }
    return res;
}

fn read_string(data: &mut VecDeque<&u8>, size: u32) -> String {
    return data.drain(0..size as usize).map(|d| std::char::from_u32(*d as u32).unwrap()).collect();
}

fn read_gamma(data: &mut VecDeque<&u8>) -> u32 {
    let res = read_uint8(data);
    if res & 0x80 == 0 {
        return res as u32;
    }
    if res & 0xC0 == 0x80 {
        return ((res & 0x3F) as u32) << 8 | read_uint8(data) as u32;
    }
    if res & 0xE0 == 0xC0 {
        return ((res & 0x1F) as u32) << 16 | read_uint16(data) as u32;
    }
    if res & 0xF0 == 0xE0 {
        return ((res & 0x0F) as u32) << 24 | (read_uint16(data) as u32) << 8 | read_uint8(data) as u32;
    }
    if res & 0xF8 == 0xF0 {
        return read_uint32(data) as u32;
    }

    console_log!("ERROR: Invalid gamma encoding");
    return 0;
}

fn read_header_table(data: &mut VecDeque<&u8>) -> Vec<(String, u8)> {
    let mut table: Vec<(String, u8)> = Vec::new();

    loop {
        let field_type = read_uint8(data);
        if field_type == 0 {
            break;
        }

        let field_length = read_gamma(data);
        let field_name = read_string(data, field_length);

        table.push((field_name, field_type));
    }

    return table;
}

fn read_header_subtables(data: &mut VecDeque<&u8>, table: &Vec<(String, u8)>, tables: &mut HashMap<String, Vec<(String, u8)>>) {
    for (field_name, field_type) in table {
        if *field_type == 0x10 | 11 {
            let table = read_header_table(data);
            read_header_subtables(data, &table, tables);
            tables.insert(field_name.clone(), table);
        }
    }
}

fn read_header(data: &mut VecDeque<&u8>) -> HashMap<String, Vec<(String, u8)>> {
    let mut tables: HashMap<String, Vec<(String, u8)>> = HashMap::new();

    let table = read_header_table(data);
    read_header_subtables(data, &table, &mut tables);
    tables.insert("root".to_string(), table);

    return tables;
}

fn read_field(data: &mut VecDeque<&u8>, tables: &HashMap<String, Vec<(String, u8)>>, field_name: &String, field_type: u8) -> Value {
    if field_type & 0x10 != 0 && field_type != (0x10 | 10) {
        let length = read_gamma(data);

        let mut record: Vec<Value> = Vec::new();

        for _ in 0..length {
            record.push(read_field(data, tables, field_name, field_type & 0xf));
        }
        return Value::List(record);
    }

    return match field_type & 0xf {
        1 => Value::I8(read_uint8(data) as i8),
        2 => Value::U8(read_uint8(data)),
        3 => Value::I16(read_uint16(data) as i16),
        4 => Value::U16(read_uint16(data)),
        5 => Value::I32(read_uint32(data) as i32),
        6 => Value::U32(read_uint32(data)),
        7 => Value::I64(read_uint64(data) as i64),
        8 => Value::U64(read_uint64(data)),
        9 => Value::U16(read_uint16(data)),
        10 => { let length = read_gamma(data); return Value::String(read_string(data, length)); },
        11 => read_record(data, tables, field_name),
        _ => { console_log!("Unknown field type {}", field_type); panic!("Unknown field type"); },
    }
}

fn read_record(data: &mut VecDeque<&u8>, tables: &HashMap<String, Vec<(String, u8)>>, key: &String) -> Value {
    let mut record: HashMap<String, Value> = HashMap::new();

    for (field_name, field_type) in &tables[key] {
        record.insert(field_name.clone(), read_field(data, tables, field_name, *field_type));
    }

    return Value::Struct(record);
}

fn read_root_record(data: &mut VecDeque<&u8>, tables: &HashMap<String, Vec<(String, u8)>>) -> Value {
    return read_record(data, tables, &"root".to_string());
}

#[wasm_bindgen]
pub fn decompress(incoming: &Uint8Array) -> String {
    let data_vec = incoming.to_vec();
    let mut data: VecDeque<&u8> = VecDeque::from_iter(&data_vec[0..8]);

    let compression = vec![read_uint8(&mut data), read_uint8(&mut data), read_uint8(&mut data), read_uint8(&mut data)];
    let compression_str: String = compression
        .into_iter()
        .map(|d| std::char::from_u32(d as u32).unwrap())
        .collect();

    if compression_str != "OTTX" {
        let error = format!("Savegame uses unsupported compression: {}", compression_str);
        return serde_json::to_string(&Savegame { error: error, ..Default::default() }).unwrap();
    }

    let revision = read_uint16(&mut data);
    read_uint16(&mut data);

    let mut savegame : Savegame = Savegame { error: "Unknown error".to_string(), revision: revision, ..Default::default() };

    if revision < 295 {
        savegame.error = format!("Savegame too old for analysis: {} < 295", revision);
        return serde_json::to_string(&savegame).unwrap();
    }

    let mut f = Cursor::new(data_vec);
    f.seek(SeekFrom::Start(8)).unwrap();

    let mut decomp_read: Vec<u8> = Vec::new();
    xz_decompress(&mut f, &mut decomp_read).unwrap();
    let mut decomp: VecDeque<&u8> = VecDeque::from_iter(&decomp_read);

    loop {
        let tag = vec![read_uint8(&mut decomp), read_uint8(&mut decomp), read_uint8(&mut decomp), read_uint8(&mut decomp)];
        if tag == [0, 0, 0, 0] {
            break;
        }

        let tag_str: String = tag
            .into_iter()
            .map(|d| std::char::from_u32(d as u32).unwrap())
            .collect();

        let m = read_uint8(&mut decomp);
        let block_mode = m & 0xf;

        if block_mode == 0 {
            let size = (m as u32 >> 4) << 24 | ((read_uint8(&mut decomp) as u32) << 16) | read_uint16(&mut decomp) as u32;
            read_bytes(&mut decomp, size);
        } else {
            let header_size = read_gamma(&mut decomp);
            let decomp_length = decomp.len() as u32;
            let tables = read_header(&mut decomp);
            if decomp_length - header_size + 1 != decomp.len() as u32 {
                savegame.error = format!("Invalid header size: {} vs {}", decomp_length - header_size + 1, decomp.len());
                return serde_json::to_string(&savegame).unwrap();
            }

            let mut records: HashMap<u32, Value> = HashMap::new();

            let mut index = -1;
            loop {
                let mut size = read_gamma(&mut decomp);
                if size == 0 {
                    break;
                }

                if block_mode == 4 {
                    let decomp_length = decomp.len() as u32;
                    index = read_gamma(&mut decomp) as i32;
                    size -= decomp_length - decomp.len() as u32;
                } else {
                    index += 1
                }

                if size > 1 {
                    let decomp_length = decomp.len() as u32;
                    let value = read_root_record(&mut decomp, &tables);
                    records.insert(index as u32, value);

                    if decomp_length - size + 1 != decomp.len() as u32 {
                        /* Two chunks have additional storage at the end of their chunk; ignore this. */
                        if tag_str == "GSDT" || tag_str == "AIPL" {
                            let done = decomp_length - (decomp.len() as u32);
                            read_bytes(&mut decomp, size - 1 - done);
                        } else {
                            savegame.error = format!("Invalid record size for {}: {} vs {}", tag_str, decomp_length - size + 1, decomp.len());
                            return serde_json::to_string(&savegame).unwrap();
                        }
                    }
                }
            }

            savegame.chunks.insert(tag_str, records);
        }
    }

    savegame.error = "".to_string();
    return serde_json::to_string(&savegame).unwrap();
}

pub fn set_panic_hook() {
    #[cfg(feature = "console_error_panic_hook")]
    console_error_panic_hook::set_once();
}
