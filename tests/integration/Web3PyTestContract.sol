// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

contract Web3PyTestContract {
    
    // Structure definitions
    struct SimpleStruct {
        uint256 id;
        string name;
        bool active;
    }
    
    struct NestedStruct {
        uint256 value;
        SimpleStruct inner;
        address owner;
    }
    
    struct ArrayStruct {
        string title;
        uint256[] numbers;
        address[] addresses;
    }
    
    // Test basic types
    // Python: contract.functions.testInt(-42).call()
    // Remix: -42
    function testInt(int256 _value) public pure returns (int256) {
        return _value * -1;
    }
    
    // Python: contract.functions.testUint(12345).call()
    // Remix: 12345
    function testUint(uint256 _value) public pure returns (uint256) {
        return _value + 100;
    }
    
    // Python: contract.functions.testAddress("0x742d35Cc6634C0532925a3b8D98D8e35ce02E52a").call()
    // Remix: "0x742d35Cc6634C0532925a3b8D98D8e35ce02E52a"
    function testAddress(address _addr) public pure returns (address) {
        return _addr;
    }
    
    // Python: contract.functions.testBytes(b'Hello World').call()
    // Remix: "0x48656c6c6f20576f726c64" or "Hello World"
    function testBytes(bytes memory _data) public pure returns (bytes memory) {
        return _data;
    }
    
    // Python: contract.functions.testBool(True).call()
    // Remix: true
    function testBool(bool _flag) public pure returns (bool) {
        return !_flag;
    }
    
    // Test arrays
    // Python: contract.functions.testUintArray([1, 2, 3, 4, 5]).call()
    // Remix: [1,2,3,4,5]
    function testUintArray(uint256[] memory _values) public pure returns (uint256[] memory) {
        uint256[] memory result = new uint256[](_values.length);
        for (uint i = 0; i < _values.length; i++) {
            result[i] = _values[i] * 2;
        }
        return result;
    }
    
    // Python: contract.functions.testAddressArray(["0x123...", "0x456..."]).call()
    // Remix: ["0x742d35Cc6634C0532925a3b8D98D8e35ce02E52a","0x8ba1f109551bD432803012645Hac136c"]
    function testAddressArray(address[] memory _addresses) public pure returns (uint256) {
        return _addresses.length;
    }
    
    // Python: contract.functions.testBytesArray([b'data1', b'data2']).call()
    // Remix: ["0x6461746131","0x6461746132"]
    function testBytesArray(bytes[] memory _data) public pure returns (uint256) {
        return _data.length;
    }
    
    // Test structure
    // Python: contract.functions.testSimpleStruct((123, "test", True)).call()
    // Python: contract.functions.testSimpleStruct({'id': 123, 'name': 'test', 'active': True}).call()
    // Remix: [123,"test",true]
    function testSimpleStruct(SimpleStruct memory _struct) public pure returns (SimpleStruct memory) {
        return SimpleStruct({
            id: _struct.id + 1,
            name: string(abi.encodePacked("Modified: ", _struct.name)),
            active: !_struct.active
        });
    }
    
    // Test nested structure
    // Python: contract.functions.testNestedStruct((100, (1, "inner", False), "0x123...")).call()
    // Remix: [100,[1,"inner",false],"0x742d35Cc6634C0532925a3b8D98D8e35ce02E52a"]
    function testNestedStruct(NestedStruct memory _nested) public pure returns (NestedStruct memory) {
        return NestedStruct({
            value: _nested.value * 10,
            inner: SimpleStruct({
                id: _nested.inner.id + 100,
                name: string(abi.encodePacked("Nested: ", _nested.inner.name)),
                active: !_nested.inner.active
            }),
            owner: _nested.owner
        });
    }
    
    // Test array of structures
    // Python: contract.functions.testStructArray([(1, "first", True), (2, "second", False)]).call()
    // Remix: [[1,"first",true],[2,"second",false]]
    function testStructArray(SimpleStruct[] memory _structs) public pure returns (uint256) {
        uint256 totalId = 0;
        for (uint i = 0; i < _structs.length; i++) {
            totalId += _structs[i].id;
        }
        return totalId;
    }
    
    // Test structure with array
    // Python: contract.functions.testArrayStruct(("title", [1, 2, 3], ["0x123...", "0x456..."])).call()
    // Remix: ["title",[1,2,3],["0x742d35Cc6634C0532925a3b8D98D8e35ce02E52a","0x8ba1f109551bD432803012645Hac136c"]]
    function testArrayStruct(ArrayStruct memory _arrayStruct) public pure returns (ArrayStruct memory) {
        uint256[] memory newNumbers = new uint256[](_arrayStruct.numbers.length);
        for (uint i = 0; i < _arrayStruct.numbers.length; i++) {
            newNumbers[i] = _arrayStruct.numbers[i] + 10;
        }
        
        return ArrayStruct({
            title: string(abi.encodePacked("Processed: ", _arrayStruct.title)),
            numbers: newNumbers,
            addresses: _arrayStruct.addresses
        });
    }
    
    // Test multiple parameters of different types
    // Python: contract.functions.testMultipleParams(-100, 200, "0x123...", True, b'data', (1, "struct", False)).call()
    // Remix: -100,200,"0x742d35Cc6634C0532925a3b8D98D8e35ce02E52a",true,"0x64617461",[1,"struct",false]
    function testMultipleParams(
        int256 _intValue,
        uint256 _uintValue,
        address _addr,
        bool _flag,
        bytes memory _data,
        SimpleStruct memory _struct
    ) public pure returns (
        int256,
        uint256,
        address,
        bool,
        bytes memory,
        SimpleStruct memory
    ) {
        return (
            _intValue,
            _uintValue,
            _addr,
            _flag,
            _data,
            _struct
        );
    }
    
    // Test fixed-size arrays
    // Python: contract.functions.testFixedArray([10, 20, 30]).call()
    // Remix: [10,20,30]
    function testFixedArray(uint256[3] memory _values) public pure returns (uint256[3] memory) {
        return [_values[0] + 1, _values[1] + 2, _values[2] + 3];
    }
    
    // Test bytes32
    // Python: contract.functions.testBytes32(b'0x' + b'1234567890abcdef' * 2).call()
    // Remix: "0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef"
    function testBytes32(bytes32 _hash) public pure returns (bytes32) {
        return keccak256(abi.encodePacked(_hash));
    }
    
    // Test string
    // Python: contract.functions.testString("World").call()
    // Remix: "World"
    function testString(string memory _text) public pure returns (string memory) {
        return string(abi.encodePacked("Hello, ", _text, "!"));
    }
    
    // Test enum (if needed)
    enum Status { Pending, Active, Inactive }
    
    // Python: contract.functions.testEnum(0).call()  # 0=Pending, 1=Active, 2=Inactive
    // Remix: 0
    function testEnum(Status _status) public pure returns (Status) {
        if (_status == Status.Pending) return Status.Active;
        if (_status == Status.Active) return Status.Inactive;
        return Status.Pending;
    }
}