export const findAirline = ( dataset, word ) => {
  // console.log('in find airline func', dataset, word);
  let set = dataset;
  let len = set.length;
  let w = word;

  let result = null;

  for (let i = 0;i < len;) {
    if ( set[i].companyName === w ) {
      result = set[i].codeIATA;
      return result;
    }
    else i++;
  }
};


export const findAirport = ( dataset, word ) => {
  // console.log('in find airport func', dataset, word);
  let set = dataset;
  let len = set.length;
  let w = word;

  let result = null;

  for (let i = 0;i < len;) {
    if ( set[i].airportName === w ) {
      result = set[i].codeAirport;
      return result;
    }
    else i++;
  }
};