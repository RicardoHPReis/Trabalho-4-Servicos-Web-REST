<template>
  <div>
    <input type="number" v-model="numero1">
    <input type="number" v-model="numero2">
    <button @click="calcular">Calcular</button>
    <p>Resultado: {{ resultado }}</p>
  </div>
</template>

<script>
export default {
  data() {
    return {
      numero1: 0,
      numero2: 0,
      resultado: null
    };
  },
  methods: {
    async calcular() {
      try {
        const response = await fetch('/calcular', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({ numero1: this.numero1, numero2: this.numero2 })
        });
        const data = await response.json();
        this.resultado = data.resultado;
      } catch (error) {
        console.error('Erro ao chamar a API:', error);
      }
    }
  }
};
</script>