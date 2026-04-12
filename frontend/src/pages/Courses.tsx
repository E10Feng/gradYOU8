import { useState } from 'react'

interface Course {
  id: string
  title: string
  credits: number
  department: string
  description: string
}

const SAMPLE_COURSES: Course[] = [
  { id: "BIOL 296", title: "Biochemistry I", credits: 3, department: "Biology", description: "First semester of a two-semester introductory biochemistry sequence. Topics include protein structure, enzyme kinetics, metabolism, and molecular biology." },
  { id: "BIOL 297", title: "Biochemistry II", credits: 3, department: "Biology", description: "Continuation of BIOL 296. Topics include DNA replication, transcription, translation, and gene regulation." },
  { id: "BIOL 305", title: "Cell Biology", credits: 3, department: "Biology", description: "Structure and function of eukaryotic cells. Topics include membrane transport, organelle biology, cell signaling, and the cytoskeleton." },
  { id: "BIOL 310", title: "Genetics", credits: 3, department: "Biology", description: "Principles of Mendelian and molecular genetics. Topics include gene mapping, transcription, translation, and genetic engineering." },
  { id: "BIOL 350", title: "Evolution", credits: 3, department: "Biology", description: "Mechanisms of evolution including natural selection, genetic drift, mutation, and speciation." },
  { id: "CHEM 111", title: "General Chemistry I", credits: 3, department: "Chemistry", description: "Introduction to chemical principles including atomic structure, bonding, stoichiometry, and thermodynamics." },
  { id: "CHEM 112", title: "General Chemistry II", credits: 3, department: "Chemistry", description: "Continuation of CHEM 111. Topics include kinetics, equilibrium, acid-base chemistry, and electrochemistry." },
  { id: "CHEM 261", title: "Organic Chemistry I", credits: 3, department: "Chemistry", description: "Structure, bonding, and reactivity of organic compounds. Stereochemistry and mechanism introduction." },
  { id: "CHEM 262", title: "Organic Chemistry II", credits: 3, department: "Chemistry", description: "Continuation of CHEM 261. More complex reactions, spectroscopy, and multi-step synthesis." },
  { id: "CHEM 401", title: "Biochemistry I", credits: 3, department: "Chemistry", description: "Structure and function of biomolecules. Protein folding, enzyme catalysis, and metabolic pathways." },
  { id: "CSE 131", title: "Computer Science I", credits: 3, department: "Computer Science", description: "Introduction to computer science and programming. Topics include algorithms, data structures, and object-oriented programming in Python." },
  { id: "CSE 132", title: "Computer Science II", credits: 3, department: "Computer Science", description: "Continuation of CSE 131. Data structures, recursion, complexity, and software development practices." },
  { id: "CSE 240", title: "Logic for Computer Science", credits: 3, department: "Computer Science", description: "Propositional and predicate logic, proof techniques, and their applications in computer science." },
  { id: "CSE 247", title: "Data Structures and Algorithms", credits: 3, department: "Computer Science", description: "Advanced data structures including trees, graphs, and hash tables. Algorithm analysis and design." },
  { id: "CSE 330", title: "Operating Systems", credits: 3, department: "Computer Science", description: "Process management, memory management, file systems, and concurrency. Modern OS design principles." },
  { id: "CSE 340", title: "Applied Probability", credits: 3, department: "Computer Science", description: "Probability theory and applications in computer science. Random variables, distributions, and expectation." },
  { id: "MATH 131", title: "Calculus I", credits: 3, department: "Mathematics", description: "Differential calculus of single-variable functions. Limits, derivatives, and applications." },
  { id: "MATH 132", title: "Calculus II", credits: 3, department: "Mathematics", description: "Integral calculus and infinite series. Techniques of integration and applications." },
  { id: "MATH 2200", title: "Calculus III", credits: 3, department: "Mathematics", description: "Multivariable calculus. Topics include vectors, partial derivatives, multiple integrals, and vector calculus." },
  { id: "MATH 310", title: "Linear Algebra", credits: 3, department: "Mathematics", description: "Vector spaces, linear transformations, matrices, eigenvalues, and applications." },
  { id: "MATH 310", title: "Foundations of Arithmetic", credits: 3, department: "Mathematics", description: "Number systems, algebra, geometry, and data analysis for elementary education." },
  { id: "PHYSICS 197", title: "Physics I for Engineers", credits: 3, department: "Physics", description: "First semester of calculus-based physics for engineering students. Mechanics, waves, and thermodynamics." },
  { id: "PHYSICS 198", title: "Physics II for Engineers", credits: 3, department: "Physics", description: "Continuation of PHYSICS 197. Electricity, magnetism, and optics." },
  { id: "PHYSICS 205", title: "Modern Physics", credits: 3, department: "Physics", description: "Introduction to relativity and quantum mechanics. Wave-particle duality, atomic physics, and nuclear physics." },
  { id: "L101", title: "Elementary Spanish I", credits: 3, department: "Language", description: "Beginning Spanish for students with no prior background." },
  { id: "L102", title: "Elementary Spanish II", credits: 3, department: "Language", description: "Continuation of L101. Grammar, vocabulary, and conversational skills development." },
  { id: "L201", title: "Intermediate Spanish I", credits: 3, department: "Language", description: "Intermediate Spanish emphasizing reading, writing, and cultural understanding." },
  { id: "L211", title: "Spanish for Heritage Speakers", credits: 3, department: "Language", description: "Designed for students with family background in Spanish. Reading and writing focus." },
  { id: "ECON 101", title: "Introduction to Microeconomics", credits: 3, department: "Economics", description: "Introduction to economic analysis including supply and demand, consumer behavior, and market structures." },
  { id: "ECON 102", title: "Introduction to Macroeconomics", credits: 3, department: "Economics", description: "Aggregate economic analysis including GDP, inflation, unemployment, and monetary policy." },
  { id: "ECON 301", title: "Microeconomic Theory", credits: 3, department: "Economics", description: "Advanced consumer and producer theory, general equilibrium, and welfare economics." },
  { id: "ECON 302", title: "Macroeconomic Theory", credits: 3, department: "Economics", description: "Dynamic macro models, economic growth, and policy analysis." },
  { id: "PSYCH 100", title: "Introduction to Psychology", credits: 3, department: "Psychology", description: "Survey of psychology including development, learning, memory, personality, and abnormal behavior." },
  { id: "PSYCH 220", title: "Psychological Statistics", credits: 3, department: "Psychology", description: "Statistical methods for psychological research. Hypothesis testing, ANOVA, and regression." },
  { id: "PSYCH 303", title: "Cognitive Neuroscience", credits: 3, department: "Psychology", description: "Brain mechanisms underlying perception, attention, memory, and language." },
  { id: "POL SCI 101", title: "Introduction to American Politics", credits: 3, department: "Political Science", description: "Foundations of American government including Congress, presidency, courts, and political behavior." },
  { id: "POL SCI 201", title: "Research Methods", credits: 3, department: "Political Science", description: "Research design, quantitative methods, and data analysis in political science." },
  { id: "HIST 101", title: "Ancient Civilizations", credits: 3, department: "History", description: "Greek, Roman, and Near Eastern civilizations from antiquity to the fall of Rome." },
  { id: "HIST 102", title: "Medieval Europe", credits: 3, department: "History", description: "European civilization from the fall of Rome to the Renaissance." },
  { id: "PHIL 100", title: "Introduction to Philosophy", credits: 3, department: "Philosophy", description: "Major philosophical problems including knowledge, reality, truth, and value." },
  { id: "PHIL 301", title: "Ethics", credits: 3, department: "Philosophy", description: "Theoretical and applied ethics. Moral reasoning and contemporary ethical issues." },
]

const DEPARTMENTS = [...new Set(SAMPLE_COURSES.map(c => c.department))].sort()

export default function Courses() {
  const [search, setSearch] = useState('')
  const [selectedDept, setSelectedDept] = useState<string | null>(null)
  const [expandedId, setExpandedId] = useState<string | null>(null)

  const filtered = SAMPLE_COURSES.filter(c => {
    const matchesSearch = search === '' ||
      c.id.toLowerCase().includes(search.toLowerCase()) ||
      c.title.toLowerCase().includes(search.toLowerCase()) ||
      c.department.toLowerCase().includes(search.toLowerCase())
    const matchesDept = selectedDept === null || c.department === selectedDept
    return matchesSearch && matchesDept
  })

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-3xl font-semibold tracking-tight mb-2" style={{ color: 'var(--text-primary)' }}>Course Catalog</h1>
        <p className="text-sm text-[color:var(--text-muted)] leading-relaxed">
          Browse popular WashU courses. Click a course to see its description.
        </p>
      </div>

      <div className="flex flex-col gap-3">
        <input
          type="text"
          value={search}
          onChange={e => setSearch(e.target.value)}
          placeholder="Search by course code, title, or department..."
          className="w-full glass-input rounded-lg px-4 py-3 text-sm placeholder-[color:var(--text-subtle)]"
          style={{ color: 'var(--text-primary)' }}
        />

        <div className="flex flex-wrap gap-2">
          <button
            onClick={() => setSelectedDept(null)}
            className={`px-3 py-1.5 rounded-full text-xs font-medium transition ${
              selectedDept === null ? 'glass-button text-white' : 'glass-chip transition-colors'
            }`}
            style={selectedDept !== null ? { color: 'var(--text-muted)' } : undefined}
          >
            All
          </button>
          {DEPARTMENTS.map(dept => (
            <button
              key={dept}
              onClick={() => setSelectedDept(dept === selectedDept ? null : dept)}
              className={`px-3 py-1.5 rounded-full text-xs font-medium transition ${
                selectedDept === dept ? 'glass-button text-white' : 'glass-chip transition-colors'
              }`}
              style={selectedDept !== dept ? { color: 'var(--text-muted)' } : undefined}
            >
              {dept}
            </button>
          ))}
        </div>
      </div>

      {filtered.length === 0 ? (
        <p className="text-sm text-center py-8" style={{ color: 'var(--text-muted)' }}>No courses match your search.</p>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {filtered.map(course => (
            <div
              key={course.id}
              onClick={() => setExpandedId(expandedId === course.id ? null : course.id)}
              className="glass surface-card rounded-xl p-4 cursor-pointer transition interactive-lift"
              style={{
                border: `1px solid ${expandedId === course.id ? 'var(--satisfied-border)' : 'var(--surface-card-border)'}`,
              }}
            >
              <div className="flex items-start justify-between gap-2">
                <div>
                  <p className="font-mono text-sm font-medium" style={{ color: 'var(--accent)' }}>{course.id}</p>
                  <p className="text-sm font-medium mt-0.5" style={{ color: 'var(--text-primary)' }}>{course.title}</p>
                </div>
                <span className="text-xs glass-chip px-2 py-0.5 rounded shrink-0" style={{ color: 'var(--text-muted)' }}>
                  {course.credits} cr
                </span>
              </div>
              <p className="text-xs mt-1" style={{ color: 'var(--text-muted)' }}>{course.department}</p>
              {expandedId === course.id && (
                <p className="text-xs mt-3 pt-3" style={{ color: 'var(--text-muted)', borderTop: '1px solid var(--glass-border)' }}>{course.description}</p>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}