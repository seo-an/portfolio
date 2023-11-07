import React, { useState } from 'react';

const UserInput = ({ onSearch }) => {
  const [inputValue, setInputValue] = useState('');

  const handleSearch2 = (d) => {
		console.log('handle2', d)
    onSearch(inputValue);
  };

  return (
    <div>
      <input
        type="text"
        value={inputValue}
        onChange={(e) => setInputValue(e.target.value)}
      />
      <button onClick={handleSearch2}>검색</button>
    </div>
  );
};

export default UserInput;