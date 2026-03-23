const { MongoClient } = require('mongodb');

async function main() {
    const uri = "mongodb+srv://door2fy:door2fy@cluster0.z5i6p.mongodb.net/door2fy";
    const client = new MongoClient(uri);

    try {
        await client.connect();
        const database = client.db('door2fy');
        const profiles = database.collection('profiles');

        const profile = await profiles.findOne({});
        console.log(JSON.stringify(profile, null, 2));
    } finally {
        await client.close();
    }
}

main().catch(console.error);
