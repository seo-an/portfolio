interface GreetFunction {
  (name: string, age: number): string;
}

const greet: GreetFunction = (name, age) => {
  return `Hello, my name is ${name} and I am ${age} years old.`;
};

export default greet;