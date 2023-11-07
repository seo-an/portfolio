import React, { useState } from 'react';
import UserInput from './UserInput';
import searchData from './searchUtils';

const TestComponent = () => {
  const [searchResult, setSearchResult] = useState('');

  const handleSearch1 = (d) => {
    // Action의 searchData 함수를 호출하여 검색을 수행합니다.
    console.log('handle1', d);
    const result = searchData(d);
    setSearchResult(result);
  };

  return (
    <div>
      <h1>검색 앱</h1>
      <UserInput onSearch={handleSearch1} />
      <div>
        <h2>검색 결과:</h2>
        <p>{searchResult}</p>
      </div>
    </div>
  );
};

export default TestComponent;